import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export type SmtpCapture = {
  host: string;
  port: number;
  verificationUrl(recipient: string): Promise<string>;
  close(): Promise<void>;
};

function decodeMessage(raw: string): string {
  return raw
    .replace(/=\r?\n/g, "")
    .replace(/=3D/gi, "=")
    .replace(/&amp;/g, "&");
}

const captureScript = String.raw`
const net = require("node:net");
const port = Number(process.argv[1]);
const server = net.createServer((socket) => {
  socket.setEncoding("utf8");
  socket.write("220 gustav-e2e-smtp ESMTP\r\n");
  let buffer = "";
  let dataMode = false;
  let message = "";
  socket.on("data", (chunk) => {
    buffer += chunk;
    while (true) {
      if (dataMode) {
        const end = buffer.indexOf("\r\n.\r\n");
        if (end < 0) return;
        message += buffer.slice(0, end);
        process.stdout.write("MESSAGE " + Buffer.from(message).toString("base64") + "\n");
        buffer = buffer.slice(end + 5);
        dataMode = false;
        message = "";
        socket.write("250 2.0.0 queued\r\n");
        continue;
      }
      const lineEnd = buffer.indexOf("\r\n");
      if (lineEnd < 0) return;
      const line = buffer.slice(0, lineEnd);
      buffer = buffer.slice(lineEnd + 2);
      const command = line.toUpperCase();
      if (command.startsWith("EHLO") || command.startsWith("HELO")) {
        socket.write("250-gustav-e2e-smtp\r\n250 SIZE 10485760\r\n");
      } else if (command.startsWith("DATA")) {
        dataMode = true;
        socket.write("354 End data with <CR><LF>.<CR><LF>\r\n");
      } else if (command.startsWith("QUIT")) {
        socket.end("221 2.0.0 bye\r\n");
      } else {
        socket.write("250 2.0.0 ok\r\n");
      }
    }
  });
});
server.listen(port, "0.0.0.0", () => process.stdout.write("READY\n"));
process.on("SIGTERM", () => server.close(() => process.exit(0)));
`;

async function startCaptureProcess(port: number, messages: string[]): Promise<ChildProcessWithoutNullStreams> {
  const child = spawn("docker", [
    "exec", "-i", "gustav-frontend", "node", "-e", captureScript, String(port)
  ]);
  child.stderr.setEncoding("utf8");
  child.stdout.setEncoding("utf8");
  await new Promise<void>((resolve, reject) => {
    let stdoutBuffer = "";
    const timeout = setTimeout(() => reject(new Error("smtp_capture_start_timeout")), 10_000);
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`smtp_capture_exited_${code ?? "signal"}`)));
    child.stdout.on("data", (chunk: string) => {
      stdoutBuffer += chunk;
      const lines = stdoutBuffer.split("\n");
      stdoutBuffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line === "READY") {
          clearTimeout(timeout);
          resolve();
        } else if (line.startsWith("MESSAGE ")) {
          messages.push(Buffer.from(line.slice(8), "base64").toString("utf8"));
        }
      }
    });
  });
  return child;
}

export async function startSmtpCapture(port = 25_000 + Math.floor(Math.random() * 10_000)): Promise<SmtpCapture> {
  const messages: string[] = [];
  const child = await startCaptureProcess(port, messages);

  return {
    host: "gustav-frontend",
    port,
    async verificationUrl(recipient: string): Promise<string> {
      const deadline = Date.now() + 30_000;
      while (Date.now() < deadline) {
        const raw = messages.find((candidate) =>
          candidate.toLowerCase().includes(recipient.toLowerCase())
        );
        if (raw) {
          const decoded = decodeMessage(raw);
          const match = decoded.match(/https:\/\/id\.localhost[^\s<>'"]+/);
          if (match) return match[0];
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      throw new Error("verification_mail_not_received");
    },
    async close(): Promise<void> {
      if (child.exitCode !== null) return;
      child.kill("SIGTERM");
      await new Promise<void>((resolve) => child.once("exit", () => resolve()));
    }
  };
}
