{
  self,
  pkgs,
  inputs,
}:
pkgs.mkShell {
  name = "CTO-shell";
  packages = with pkgs; [
    bash
    git
    (python310.withPackages (p:
      with p; [
        jupyterlab
        caldav
      ]))
  ];
}
