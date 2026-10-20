# Children start with default signals: python's ignored SIGPIPE survives exec
# and turned every early-closed pipe in a child into "Broken pipe" noise.

from archinstoo.lib.general import SysCommand


def test_child_pipeline_closes_quietly() -> None:
	out = SysCommand(['/bin/sh', '-c', 'yes | head -n1']).decode()

	assert out.strip() == 'y'
