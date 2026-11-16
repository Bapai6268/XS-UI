# dev.3 readiness hotfix

The published dev.3 checker never grepped journal ERROR lines. The optional Naive warning is not a readiness failure. The checker incorrectly rejected public wildcard listener representations (`*`, `[::]`, `::`) used by ss/Go on some Linux systems. The exact cause on the reported VPS still requires its diagnostic output.

Accept those public management bindings while keeping subscription/private-mode bindings loopback-only. Retain authenticated login and core running=true checks. Report the actual failure reason without printing credentials or HTTP bodies; allow 30 attempts and make logout cleanup best effort.

The root install.sh embeds the matching revised checker after verifying/extracting the original dev.3 archive and before running install-local.sh. Thus updating main fixes future fresh installs without changing the immutable release asset or bypassing its SHA-256 check. Existing installations are not overwritten. No binary change and no new release are required.

Validation: 13 Python tests passed, including wildcard formats, private subscription restriction, Naive warning with healthy core, stopped core, bad login, missing listener, logout failure, and embedded/source parity. bash -n install.sh passed. Full Ubuntu 24.04 VPS install still needs validation.
