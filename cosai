#!/bin/bash
# assumes root in an ISO env with internet con

curl -O https://mirror.cachyos.org/cachyos-repo.tar.xz
tar xvf cachyos-repo.tar.xz && cd cachyos-repo
cp cachyos-repo.sh cachyos-repo-noupdate.sh
sed -i 's/pacman -Syu/#pacman -Syu # Disabled for ISO/' cachyos-repo-noupdate.sh
./cachyos-repo-noupdate.sh

curl -L -O https://github.com/h8d13/archinstall-patch/archive/refs/heads/dot-cosai.tar.gz
tar xvf dot-cosai.tar.gz && cd archinstall-patch-dot-cosai
python -m archinstall