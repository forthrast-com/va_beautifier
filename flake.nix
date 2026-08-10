{
  description = "Vatican document parser and single-file HTML renderer";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python312.withPackages (ps: [
            ps.beautifulsoup4
          ]);
        in {
          default = pkgs.mkShellNoCC {
            packages = [
              python
              pkgs.gnumake
              pkgs.pandoc
              pkgs.typst
              pkgs.libertinus
              # Only for `tools/agent-browser`, which QAs the built readers in
              # a real browser. Nothing in the build or test path needs node —
              # but the flake shell replaces PATH wholesale, so without it
              # there is no node *and* no `nix-shell` to fetch one, and
              # browser QA becomes a yak shave from inside the dev shell.
              pkgs.nodejs
              # pdftotext, for the one Latin edition published only as a
              # PDF (Verbum Domini) — see tools/marker_parity.py.
              pkgs.poppler-utils
            ];
            shellHook = ''
              if [[ -z "''${CI:-}" ]] && git rev-parse --git-dir >/dev/null 2>&1; then
                hooks_path="$(git config --local --get core.hooksPath || true)"
                if [[ "$hooks_path" != ".githooks" ]]; then
                  git config --local core.hooksPath .githooks
                fi
              fi
            '';
          };
        });
    };
}
