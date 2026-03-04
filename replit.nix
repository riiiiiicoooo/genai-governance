{ pkgs }:

{
  deps = [
    pkgs.python310
    pkgs.python310Packages.pip
    pkgs.python310Packages.virtualenv
    pkgs.nodejs_18
    pkgs.npm
    pkgs.postgresql
    pkgs.git
  ];

  env = {
    PYTHONPATH = "/root/.cache/pip";
  };
}
