export type SessionBootstrapUser = {
  sub: string;
  name: string;
  role: string;
  roles: string[];
};

export type SessionBootstrap = {
  user: SessionBootstrapUser;
  start_target: "/learning" | "/teaching";
  spaces: string[];
};
