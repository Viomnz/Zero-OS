import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway
from zero_os.native_store_backend import issue_token, validate_token


class NativeAppStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_store_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

        pkg = self.base / "pkg"
        (pkg / "builds").mkdir(parents=True, exist_ok=True)
        (pkg / "metadata").mkdir(parents=True, exist_ok=True)
        (pkg / "signature").mkdir(parents=True, exist_ok=True)
        (pkg / "builds" / "linux_x64.bin").write_bytes(b"bin")
        (pkg / "signature" / "developer.sig").write_text("sig", encoding="utf-8")
        manifest = {"name": "NativeCalc", "version": "1.0", "targets": {"linux": "builds/linux_x64.bin"}}
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.highway.dispatch("store publish pkg", cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_native_store_install_upgrade_uninstall(self) -> None:
        s = self.highway.dispatch("native store status", cwd=str(self.base))
        sdata = json.loads(s.summary)
        self.assertTrue(sdata["ok"])
        self.assertIn("toolchains", sdata)
        self.assertIn("windows", sdata["toolchains"])
        self.assertIn("linux", sdata["toolchains"])

        i = self.highway.dispatch("native store install app=NativeCalc os=linux", cwd=str(self.base))
        idata = json.loads(i.summary)
        self.assertTrue(idata["ok"])
        iid = idata["install"]["install_id"]

        u = self.highway.dispatch(f"native store upgrade id={iid} version=1.1", cwd=str(self.base))
        self.assertTrue(json.loads(u.summary)["ok"])
        rm = self.highway.dispatch(f"native store uninstall id={iid}", cwd=str(self.base))
        self.assertTrue(json.loads(rm.summary)["ok"])

    def test_native_store_enterprise_integrations(self) -> None:
        vendor = self.highway.dispatch(
            "native store scaffold vendor app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        vdata = json.loads(vendor.summary)
        self.assertTrue(vdata["ok"])
        self.assertTrue(any(path.endswith("windows\\ZeroStore.msixmanifest") or path.endswith("windows/ZeroStore.msixmanifest") for path in vdata["created"]))

        services = self.highway.dispatch("native store scaffold services", cwd=str(self.base))
        self.assertTrue(json.loads(services.summary)["ok"])

        backend_scaffold = self.highway.dispatch("native store scaffold backend", cwd=str(self.base))
        bdata = json.loads(backend_scaffold.summary)
        self.assertTrue(bdata["ok"])
        self.assertTrue(any(path.endswith("backend\\app.py") or path.endswith("backend/app.py") for path in bdata["created"]))

        gui_scaffold = self.highway.dispatch("native store scaffold gui", cwd=str(self.base))
        gdata = json.loads(gui_scaffold.summary)
        self.assertTrue(gdata["ok"])
        self.assertTrue(any(path.endswith("client\\index.html") or path.endswith("client/index.html") for path in gdata["created"]))

        desktop = self.highway.dispatch("native store desktop scaffold", cwd=str(self.base))
        ddata = json.loads(desktop.summary)
        self.assertTrue(ddata["ok"])
        self.assertTrue(any(path.endswith("desktop_shell\\index.html") or path.endswith("desktop_shell/index.html") for path in ddata["created"]))

        backend_init = self.highway.dispatch("native store backend init", cwd=str(self.base))
        self.assertTrue(json.loads(backend_init.summary)["ok"])
        backend_user = self.highway.dispatch(
            "native store backend user create id=user1 email=user1@example.com tier=pro",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(backend_user.summary)["ok"])
        backend_token = self.highway.dispatch(
            "native store backend token issue id=token1 scope=events:write",
            cwd=str(self.base),
        )
        tdata = json.loads(backend_token.summary)
        self.assertTrue(tdata["ok"])
        self.assertTrue(validate_token(str(self.base), tdata["token_secret"], "events:write"))
        backend_charge = self.highway.dispatch(
            "native store backend charge id=ch_1 user=user1 amount=9.99 currency=usd",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(backend_charge.summary)["ok"])
        backend_event = self.highway.dispatch(
            "native store backend event kind=install json={\"app\":\"NativeCalc\"}",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(backend_event.summary)["ok"])
        backend_status = self.highway.dispatch("native store backend status", cwd=str(self.base))
        bs = json.loads(backend_status.summary)
        self.assertEqual(bs["users"], 1)
        self.assertEqual(bs["charges"], 1)
        self.assertEqual(bs["events"], 1)
        self.assertEqual(bs["active_tokens"], 1)
        self.assertEqual(bs["migrations"], [1])

        backend_deploy = self.highway.dispatch("native store backend deploy scaffold", cwd=str(self.base))
        self.assertTrue(json.loads(backend_deploy.summary)["ok"])
        backup = self.highway.dispatch("native store backend backup name=pretest", cwd=str(self.base))
        backup_data = json.loads(backup.summary)
        self.assertTrue(backup_data["ok"])
        restore = self.highway.dispatch(
            f"native store backend restore path={backup_data['backup']}",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(restore.summary)["ok"])

        windows_build = self.highway.dispatch(
            "native store build windows app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        wb = json.loads(windows_build.summary)
        self.assertIn("commands", wb)
        self.assertIn("missing_tools", wb)

        linux_build = self.highway.dispatch(
            "native store build linux app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        lb = json.loads(linux_build.summary)
        self.assertIn("commands", lb)
        self.assertIn("missing_tools", lb)

        mac_build = self.highway.dispatch(
            "native store build macos app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        mb = json.loads(mac_build.summary)
        self.assertTrue(mb["ok"])
        self.assertIn("built", mb)

        mobile_build = self.highway.dispatch(
            "native store build mobile app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        mob = json.loads(mobile_build.summary)
        self.assertTrue(mob["ok"])
        self.assertEqual(len(mob["artifacts"]), 5)
        sign = self.highway.dispatch(
            f"native store artifact sign path={mob['artifacts'][0]} signer=ci",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(sign.summary)["ok"])
        verify = self.highway.dispatch(
            f"native store artifact verify path={mob['artifacts'][0]}",
            cwd=str(self.base),
        )
        verify_data = json.loads(verify.summary)
        self.assertTrue(verify_data["ok"])

        p = self.highway.dispatch("native store pipeline run app=NativeCalc os=linux format=deb", cwd=str(self.base))
        pdata = json.loads(p.summary)
        self.assertTrue(pdata["ok"])
        self.assertEqual(pdata["pipeline"]["format"], "deb")

        svc = self.highway.dispatch("native store service set os=linux enabled=off", cwd=str(self.base))
        self.assertTrue(json.loads(svc.summary)["ok"])

        trust = self.highway.dispatch(
            "native store trust channel set name=stable signed=on notarization=on",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(trust.summary)["ok"])

        notary = self.highway.dispatch(
            "native store notarize app=NativeCalc version=1.0 signer=zero-signer",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(notary.summary)["ok"])

        backend = self.highway.dispatch(
            "native store backend integrate component=payments provider=stripe enabled=on",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(backend.summary)["ok"])

        gui = self.highway.dispatch("native store gui set first_run=on deep=on", cwd=str(self.base))
        self.assertTrue(json.loads(gui.summary)["ok"])

        desktop_pkg = self.highway.dispatch(
            "native store desktop package app=NativeCalc version=1.0",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(desktop_pkg.summary)["ok"])

        secret = self.highway.dispatch(
            "native store secret set name=signing_key value=supersecret",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(secret.summary)["ok"])

        cert = self.highway.dispatch(
            "native store cert rotate name=ZeroStoreRootCA-v2",
            cwd=str(self.base),
        )
        cert_data = json.loads(cert.summary)
        self.assertEqual(cert_data["cert_lifecycle"]["active"], "ZeroStoreRootCA-v2")

        checkpoint = self.highway.dispatch(
            "native store rollback checkpoint name=pre-release",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(checkpoint.summary)["ok"])
        restore = self.highway.dispatch(
            "native store rollback restore name=pre-release",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(restore.summary)["ok"])

        incident = self.highway.dispatch(
            "native store incident open severity=sev2 summary=package pipeline regression",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(incident.summary)["ok"])

        stress = self.highway.dispatch(
            "native store stress test traffic=1000 abuse=200 failures=40",
            cwd=str(self.base),
        )
        stress_data = json.loads(stress.summary)
        self.assertTrue(stress_data["ok"])
        self.assertIn("report", stress_data)

        release = self.highway.dispatch(
            "native store release prepare version=1.0.0 channel=stable",
            cwd=str(self.base),
        )
        release_data = json.loads(release.summary)
        self.assertEqual(release_data["release"]["version"], "1.0.0")

        e2e = self.highway.dispatch(
            "native store e2e run app=NativeCalc version=1.0 traffic=1000 abuse=200 failures=40",
            cwd=str(self.base),
        )
        e2e_data = json.loads(e2e.summary)
        self.assertTrue(e2e_data["ok"])
        self.assertIn("checks", e2e_data["report"])

        maxed = self.highway.dispatch("native store maximize", cwd=str(self.base))
        self.assertTrue(json.loads(maxed.summary)["ok"])

        ent0 = self.highway.dispatch("native store enterprise status", cwd=str(self.base))
        ent0_data = json.loads(ent0.summary)
        self.assertTrue(ent0_data["ok"])
        self.assertFalse(ent0_data["readiness"]["vendor_signing"])

        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise signing set type=kms name=aws-kms key=arn:kms:key1 hsm=on",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        for channel, ident in (
            ("microsoft", "tenant1"),
            ("apple", "team1"),
            ("google_play", "proj1"),
            ("app_store_connect", "issuer1"),
        ):
            self.assertTrue(
                json.loads(
                    self.highway.dispatch(
                        f"native store enterprise vendor configure channel={channel} identity={ident}",
                        cwd=str(self.base),
                    ).summary
                )["ok"]
            )
        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise backend set replicas=3 tls=on monitoring=on alerting=on storage=on dr=multi-region",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise desktop set binary=on updater=on service=on registration=on crash=on",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise secrets set provider=vault ca=step-ca revocation=on",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise governance set oncall=alice,bob approvers=lead1,lead2 freeze=off",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        self.assertTrue(
            json.loads(
                self.highway.dispatch(
                    "native store enterprise deployed test target=prod-canary passed=on",
                    cwd=str(self.base),
                ).summary
            )["ok"]
        )
        ent1 = self.highway.dispatch("native store enterprise status", cwd=str(self.base))
        ent1_data = json.loads(ent1.summary)
        self.assertTrue(all(ent1_data["readiness"].values()))


if __name__ == "__main__":
    unittest.main()
