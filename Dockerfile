FROM python:3.14-alpine

RUN apk add --no-cache \
    parted-dev \
    gcc \
    musl-dev \
    pacman \
    arch-install-scripts \
    coreutils \
    util-linux \
    pciutils \
    # kbd \ not needed with fallback
    git \
    # filesystem support mirrors PKGBUILD optdepends
    btrfs-progs \
    dosfstools \
    e2fsprogs \
    f2fs-tools \
    xfsprogs \
    cryptsetup \
    lvm2

RUN pip install --break-system-packages pyparted

COPY . .

ENTRYPOINT ["./RUN"]
CMD ["--help"]
