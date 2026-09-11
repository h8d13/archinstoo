from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
	from archinstoo.lib.models.swap import SwapConfiguration

# Update as settings get merged into shipped defaults
# (10-arch.conf, 50-default.conf, or CONFIG_ in /proc/config.gz)
#
# Zram block: docs.kernel.org/admin-guide/blockdev/zram.html#optimizing,
#   zram only, swappiness 180 is wrong for a disk-backed swap file
#
# Network performance
#   rmem_max/wmem_max = 16M: raise socket buffer ceiling from ~208K for 1G+ links
#     ref: fasterdata.es.net/host-tuning/linux
#   tcp_rmem/tcp_wmem: raise TCP autotuning ceiling (min/default/max bytes)
#     ref: docs.redhat.com RHEL 10 network tuning guide
#   tcp_congestion_control = bbr: model-based CC, 2-25x over CUBIC on lossy paths
#     kernel default: cubic (CONFIG_DEFAULT_TCP_CONG="cubic")
#     ref: research.google/pubs/bbr-congestion-based-congestion-control-2
#   default_qdisc = fq: per-flow pacing, required for optimal BBR
#     overrides systemd 50-default.conf which sets fq_codel
#     ref: github.com/systemd/systemd/issues/9725
#   tcp_fastopen = 3: data in SYN (client+server), saves 1 RTT (RFC 7413)
#   tcp_mtu_probing = 1: work around ICMP black holes (RFC 4821)
#
# Security
#   accept_redirects = 0: block ICMP redirect MITM (CIS 3.3.2)
#   secure_redirects = 0: belt-and-suspenders with above (CIS 3.3.3)
#   use_tempaddr = 2: IPv6 privacy extensions, rotate addresses (RFC 4941)
#   kptr_restrict = 2: zero kernel pointers for all users, protects KASLR
#   yama.ptrace_scope = 1: ptrace children only (CIS 1.5.4)
#     ref: kernel.org/doc/Documentation/security/Yama.txt
#
# Performance
#   sched_autogroup_enabled = 0: inert on systemd, avoids nice(1) breakage
#     ref: lwn.net/Articles/416641
#   nmi_watchdog = 0: hard lockup detector, periodic NMIs while CPUs are
#     busy and pins a perf counter; KVM guests already default off
#     ref: docs.kernel.org/admin-guide/sysctl/kernel.html#nmi-watchdog
#   vfs_cache_pressure = 50: retain dentry/inode caches longer
#   dirty_ratio = 15: reduce worst-case write stall (default 20)
#   dirty_background_ratio = 5: earlier background flush, smoother IO (default 10)

ZRAM_DEFAULTS: Final = [
	'# Zram tuning',
	'vm.swappiness = 180',
	'vm.watermark_boost_factor = 0',
	'vm.watermark_scale_factor = 125',
	'vm.page-cluster = 0',
]

BASE_DEFAULTS: Final = [
	'# Network performance',
	'net.core.rmem_max = 16777216',
	'net.core.wmem_max = 16777216',
	'net.ipv4.tcp_rmem = 4096 87380 16777216',
	'net.ipv4.tcp_wmem = 4096 65536 16777216',
	'net.ipv4.tcp_congestion_control = bbr',
	'net.core.default_qdisc = fq',
	'net.ipv4.tcp_fastopen = 3',
	'net.ipv4.tcp_mtu_probing = 1',
	'# Security',
	'net.ipv4.conf.all.accept_redirects = 0',
	'net.ipv4.conf.default.accept_redirects = 0',
	'net.ipv4.conf.all.secure_redirects = 0',
	'net.ipv4.conf.default.secure_redirects = 0',
	'net.ipv6.conf.all.use_tempaddr = 2',
	'net.ipv6.conf.default.use_tempaddr = 2',
	'kernel.kptr_restrict = 2',
	'kernel.yama.ptrace_scope = 1',
	'# Performance',
	'kernel.sched_autogroup_enabled = 0',
	'kernel.nmi_watchdog = 0',
	'vm.vfs_cache_pressure = 50',
	'vm.dirty_ratio = 15',
	'vm.dirty_background_ratio = 5',
]


def sysctl_defaults(swap: SwapConfiguration | None) -> list[str]:
	if swap and swap.zram:
		return [*ZRAM_DEFAULTS, '', *BASE_DEFAULTS]
	return list(BASE_DEFAULTS)


# sysctl.d(5) shape: 'key = value', comments and blanks skipped
def sysctl_entries(lines: list[str]) -> dict[str, str]:
	entries: dict[str, str] = {}
	for line in lines:
		stripped = line.strip()
		if not stripped or stripped.startswith(('#', ';')):
			continue
		key, sep, value = stripped.partition('=')
		if not sep:
			raise ValueError(f'sysctl line without "=": {line!r}')
		entries[key.strip()] = value.strip()
	return entries
