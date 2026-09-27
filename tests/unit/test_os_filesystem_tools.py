"""Unit tests for SafeFilesystemTool and sandboxing boundaries."""

import tempfile

import pytest

from services.os_control.filesystem_tool import FilesystemSecurityException, SafeFilesystemTool


def test_filesystem_read_and_write() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        fs = SafeFilesystemTool(sandbox_root=tmpdir)

        # Write
        w_res = fs.write_file("sub/test.txt", "Hello PIXEL Real OS")
        assert w_res.success
        assert w_res.state_verified

        # Read
        r_res = fs.read_file("sub/test.txt")
        assert r_res.success
        assert r_res.content == "Hello PIXEL Real OS"
        assert r_res.state_verified

        # List
        l_res = fs.list_dir("sub")
        assert l_res.success
        assert "test.txt" in l_res.files

        # Delete
        d_res = fs.delete_file("sub/test.txt")
        assert d_res.success
        assert d_res.state_verified
        assert not fs.read_file("sub/test.txt").success


def test_filesystem_path_traversal_attack_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        fs = SafeFilesystemTool(sandbox_root=tmpdir)

        # Attempt to escape sandbox via parent directory traversal
        with pytest.raises(FilesystemSecurityException):
            fs._resolve_and_validate_path("../../../windows/system32/cmd.exe")

        with pytest.raises(FilesystemSecurityException):
            fs._resolve_and_validate_path("/etc/shadow")
