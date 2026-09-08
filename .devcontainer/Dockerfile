FROM archlinux/archlinux:latest

# same prep as .github/workflows/*.yaml
RUN pacman-key --init \
	&& pacman --noconfirm -Sy archlinux-keyring \
	&& pacman --noconfirm -Syu

# runtime deps from the release PKGBUILD, linters are pinned by pre-commit itself
# python-pylint: pylint hook is language: system
COPY PKGBUILD /tmp/PKGBUILD
RUN . /tmp/PKGBUILD \
	&& pacman --noconfirm -S --needed "${depends[@]}" \
		pre-commit python-pytest python-pylint \
	&& pacman --noconfirm -Scc \
	&& rm /tmp/PKGBUILD
