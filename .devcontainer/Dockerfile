FROM archlinux/archlinux:latest

# usage: docker build -t archinstoo-dev -f .devcontainer/Dockerfile installer

# same prep as .github/workflows/*.yaml
RUN pacman-key --init \
	&& pacman --noconfirm -Sy archlinux-keyring \
	&& pacman --noconfirm -Syu

# runtime deps from the release PKGBUILD, linters are pinned by pre-commit itself
COPY PKGBUILD /tmp/PKGBUILD
RUN . /tmp/PKGBUILD \
	&& pacman --noconfirm -S --needed "${depends[@]}" "${makedepends[@]}" \
	&& pacman --noconfirm -Scc \
	&& rm /tmp/PKGBUILD
