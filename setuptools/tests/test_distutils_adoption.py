import os
import sys
import functools
import subprocess
import platform

import pytest
import jaraco.envs
import path


IS_PYPY = '__pypy__' in sys.builtin_module_names

# find_distutils() below launches the venv interpreter with a deliberately
# minimal environment (only SETUPTOOLS_USE_DISTUTILS and SYSTEMROOT). A PyPy
# venv on Windows resolves libpypy3-c.dll and its sibling DLLs through PATH,
# so with PATH stripped the child dies at image-load time with
# STATUS_DLL_NOT_FOUND (0xc0000135) before any distutils import happens.
# The tests marked with this still run on the CPython Windows legs and on the
# PyPy Linux leg, so both the platform and the interpreter stay covered.
pypy_on_windows = pytest.mark.skipif(
    IS_PYPY and platform.system() == 'Windows',
    reason="a PyPy venv on Windows cannot load its DLLs without PATH",
)


class VirtualEnv(jaraco.envs.VirtualEnv):
    name = '.env'

    def run(self, cmd, *args, **kwargs):
        cmd = [self.exe(cmd[0])] + cmd[1:]
        return subprocess.check_output(cmd, *args, cwd=self.root, **kwargs)


@pytest.fixture
def venv(tmp_path, tmp_src):
    env = VirtualEnv()
    env.root = path.Path(tmp_path / 'venv')
    env.req = str(tmp_src)
    return env.create()


def popen_text(call):
    """
    Augment the Popen call with the parameters to ensure unicode text.
    """
    return functools.partial(call, universal_newlines=True) \
        if sys.version_info < (3, 7) else functools.partial(call, text=True)


def find_distutils(venv, imports='distutils', env=None, **kwargs):
    py_cmd = 'import {imports}; print(distutils.__file__)'.format(**locals())
    cmd = ['python', '-c', py_cmd]
    if platform.system() == 'Windows':
        env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
    return popen_text(venv.run)(cmd, env=env, **kwargs)


@pypy_on_windows
def test_distutils_stdlib(venv):
    """
    Ensure stdlib distutils is used when appropriate.
    """
    env = dict(SETUPTOOLS_USE_DISTUTILS='stdlib')
    assert venv.name not in find_distutils(venv, env=env).split(os.sep)


@pypy_on_windows
def test_distutils_local_with_setuptools(venv):
    """
    Ensure local distutils is used when appropriate.
    """
    env = dict(SETUPTOOLS_USE_DISTUTILS='local')
    loc = find_distutils(venv, imports='setuptools, distutils', env=env)
    assert venv.name in loc.split(os.sep)


@pytest.mark.xfail('IS_PYPY', reason='pypy imports distutils on startup')
def test_distutils_local(venv):
    """
    Even without importing, the setuptools-local copy of distutils is
    preferred.
    """
    env = dict(SETUPTOOLS_USE_DISTUTILS='local')
    assert venv.name in find_distutils(venv, env=env).split(os.sep)
