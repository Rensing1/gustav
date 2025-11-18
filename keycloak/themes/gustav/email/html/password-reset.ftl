<#-- 
  GUSTAV password reset template (German, minimalistic).

  Intent:
    - Provide a simple reset link when a user has requested a new password.
    - Keep tone friendly, neutral and suitable for students and teachers.
-->
<!DOCTYPE html>
<html lang="de">
  <head>
    <meta charset="UTF-8" />
    <title>Passwort zurücksetzen – GUSTAV</title>
  </head>
  <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color: #f5f5f5; margin: 0; padding: 24px;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 24px; border-radius: 8px;">
      <tr>
        <td>
          <h1 style="font-size: 20px; margin: 0 0 16px 0;">Passwort zurücksetzen</h1>
          <p style="margin: 0 0 12px 0;">
            Hallo,
          </p>
          <p style="margin: 0 0 16px 0;">
            du hast angefordert, dein Passwort für die GUSTAV-Lernplattform zurückzusetzen.
          </p>
          <p style="margin: 0 0 24px 0; text-align: center;">
            <a href="${link}" style="display: inline-block; padding: 10px 18px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 4px;">
              Passwort zurücksetzen
            </a>
          </p>
          <p style="margin: 0 0 16px 0; font-size: 13px; color: #555555;">
            Falls der Button nicht funktioniert, kannst du auch diesen Link in die Adresszeile deines Browsers kopieren:<br />
            <span style="word-break: break-all;">${link}</span>
          </p>
          <p style="margin: 24px 0 8px 0; font-size: 13px; color: #555555;">
            Wenn du dein Passwort nicht zurücksetzen wolltest, kannst du diese E-Mail ignorieren.
          </p>
          <p style="margin: 0 0 8px 0; font-size: 13px; color: #555555;">
            Bei Fragen melde dich unter: <a href="mailto:support@school.example">support@school.example</a>
          </p>
          <p style="margin: 0; font-size: 12px; color: #888888;">
            GUSTAV – deine KI-unterstützte Lernplattform
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
