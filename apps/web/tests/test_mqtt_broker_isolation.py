import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REQUIRED_TOOLS = ("mosquitto", "mosquitto_ctrl", "mosquitto_pub", "mosquitto_sub")
PLUGIN_PATH = Path("/usr/lib/x86_64-linux-gnu/mosquitto_dynamic_security.so")


def _find_free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@unittest.skipUnless(
    all(shutil.which(tool) for tool in REQUIRED_TOOLS) and PLUGIN_PATH.exists(),
    "Mosquitto dynamic-security tools are not installed.",
)
class MosquittoGatewayIsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.port = _find_free_port()
        self.dynsec_path = Path(self.tmpdir.name) / "dynamic-security.json"
        self.conf_path = Path(self.tmpdir.name) / "mosquitto.conf"
        subprocess.run(
            ["mosquitto_ctrl", "dynsec", "init", str(self.dynsec_path), "admin", "adminpass"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.conf_path.write_text(
            "\n".join(
                [
                    f"listener {self.port} 127.0.0.1",
                    "allow_anonymous false",
                    f"plugin {PLUGIN_PATH}",
                    f"plugin_opt_config_file {self.dynsec_path}",
                    "",
                ]
            )
        )
        self.proc = subprocess.Popen(
            ["mosquitto", "-c", str(self.conf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._wait_for_broker()
        self._configure_dynsec()

    def tearDown(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.tmpdir.cleanup()

    def _ctrl(self, *args):
        result = subprocess.run(
            [
                "mosquitto_ctrl",
                "-h",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-u",
                "admin",
                "-P",
                "adminpass",
                "dynsec",
                *args,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            self.fail(f"mosquitto_ctrl {' '.join(args)} failed: {result.stderr or result.stdout}")
        return result

    def _wait_for_broker(self):
        for _ in range(30):
            result = subprocess.run(
                [
                    "mosquitto_ctrl",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(self.port),
                    "-u",
                    "admin",
                    "-P",
                    "adminpass",
                    "dynsec",
                    "listRoles",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                return
            time.sleep(0.1)
        stdout, stderr = self.proc.communicate(timeout=1)
        self.fail(f"Mosquitto did not start. stdout={stdout} stderr={stderr}")

    def _configure_dynsec(self):
        self._ctrl("createRole", "gateway")
        self._ctrl("createRole", "cloud-internal")
        self._ctrl("addRoleACL", "cloud-internal", "subscribePattern", "#", "allow")
        self._ctrl("addRoleACL", "cloud-internal", "publishClientSend", "#", "allow")
        self._ctrl("createClient", "novena-hub", "-p", "hubpass")
        self._ctrl("addClientRole", "novena-hub", "cloud-internal")

        for serial in ("GW-A", "GW-B"):
            role = f"gw-{serial}"
            self._ctrl("createRole", role)
            for suffix in ("telemetry", "logs", "attributes", "rpc/response"):
                self._ctrl("addRoleACL", role, "publishClientSend", f"v1/gateway/{serial}/{suffix}", "allow")
            self._ctrl("createClient", serial, "-p", f"{serial}-pass")
            self._ctrl("addClientRole", serial, "gateway")
            self._ctrl("addClientRole", serial, role)

    def _publish(self, username, password, topic):
        return subprocess.run(
            [
                "mosquitto_pub",
                "-h",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-u",
                username,
                "-P",
                password,
                "-V",
                "mqttv5",
                "-q",
                "1",
                "-t",
                topic,
                "-m",
                "{}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )

    def test_gateway_publish_acl_is_serial_scoped(self):
        allowed = self._publish("GW-A", "GW-A-pass", "v1/gateway/GW-A/telemetry")
        wrong_gateway = self._publish("GW-A", "GW-A-pass", "v1/gateway/GW-B/telemetry")
        legacy_shared = self._publish("GW-A", "GW-A-pass", "v1/gateway/telemetry")

        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertNotIn("Not authorized", allowed.stderr)
        self.assertIn("Not authorized", wrong_gateway.stderr)
        self.assertIn("Not authorized", legacy_shared.stderr)

    def test_cloud_internal_can_subscribe_to_scoped_gateway_topics(self):
        subscriber = subprocess.Popen(
            [
                "mosquitto_sub",
                "-h",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-u",
                "novena-hub",
                "-P",
                "hubpass",
                "-t",
                "v1/gateway/+/telemetry",
                "-C",
                "1",
                "-W",
                "5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.2)
        published = self._publish("GW-A", "GW-A-pass", "v1/gateway/GW-A/telemetry")
        stdout, stderr = subscriber.communicate(timeout=10)

        self.assertEqual(published.returncode, 0, published.stderr)
        self.assertEqual(subscriber.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "{}")
