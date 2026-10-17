# flake.nix
# Usage: nix develop
# clone <url> cd
# sudo nix develop --extra-experimental-features 'nix-command flakes' --command ./RUN
{
	inputs = {
		nixpkgs.url     = "github:NixOS/nixpkgs/nixos-unstable";
		flake-utils.url = "github:numtide/flake-utils";
	};

	outputs = { self, nixpkgs, flake-utils, ... }:
		flake-utils.lib.eachDefaultSystem (system: let
			overlays = [ ];
			pkgs = import nixpkgs {
				inherit system overlays;
			};
		in {
			devShells.default = pkgs.mkShell {
				buildInputs = with pkgs; [
					# Core
					pacman
					arch-install-scripts
					git
					parted

					(python314.withPackages (ps: [ ps.pyparted ]))

					# Filesystem tools
					dosfstools
					e2fsprogs
					btrfs-progs
					xfsprogs
					f2fs-tools
					cryptsetup
					lvm2

					# Utils
					coreutils
					util-linux
					pciutils
					kbd
					tzdata
					xkeyboard-config
				];

				shellHook = ''
					export TZDIR=${pkgs.tzdata}/share/zoneinfo
					# xkeyboard-config ships no binary, so the keymap lists have
					# nothing to find it by; libxkbcommon's own variable is how
					# every other reader locates the registry
					export XKB_CONFIG_ROOT=${pkgs.xkeyboard-config}/share/X11/xkb
				'';
			};
		}
	);
}
