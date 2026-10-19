#!/bin/sh
# Only this certificate; never modifies nginx configuration.
set -eu
[ "${RENEWED_LINEAGE:-}" = /etc/letsencrypt/live/design-studio-review ] || exit 0
/usr/sbin/nginx -t
systemctl reload nginx
