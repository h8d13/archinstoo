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
					libxcrypt
					tzdata
				];

				# libxcrypt is dlopen'd by crypt.py via ctypes; buildInputs only
				# wires link-time, so expose it on the runtime linker path for
				# the .so lookup.
				shellHook = ''
					export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [ pkgs.libxcrypt ]}:$LD_LIBRARY_PATH
				'';
			};
		}
	);
}
