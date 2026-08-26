#!/bin/bash
# BioGuard dual-network switch (macOS).
#
#   sudo scripts/bioguard-net.sh on      Wi-Fi joins the board's AP on a static
#                                        IP; the internet keeps flowing over USB
#                                        Ethernet or iPhone USB
#   sudo scripts/bioguard-net.sh off     Wi-Fi back to DHCP, service order restored
#        scripts/bioguard-net.sh status  read-only, needs no sudo
#
# Why a script and not four typed commands: macOS takes its default route from
# the HIGHEST-PRIORITY ACTIVE service. Join the board's AP while Wi-Fi outranks
# the uplink and the 192.168.4.1 gateway becomes the default route — the board
# works and the internet dies. This orders the services first, then joins, then
# proves all three facts (board reachable, internet reachable, default route not
# on Wi-Fi) instead of leaving you to discover a half-working state later.
set -uo pipefail

AP_SSID="BioGuard"
AP_PASS="claude_plan"
WIFI_SVC="Wi-Fi"
WIFI_DEV="en0"
STATIC_IP="192.168.4.2"
STATIC_MASK="255.255.255.0"
BOARD_IP="192.168.4.1"
STATE="${HOME}/.bioguard-net-order"

die() { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }
ok()  { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn(){ printf '\033[33m!\033[0m %s\n' "$1"; }

need_root() { [ "$(id -u)" -eq 0 ] || die "run it with sudo: sudo $0 $1"; }

# service name -> BSD device, straight from the service order table
dev_of() {
  networksetup -listnetworkserviceorder | awk -v s="$1" '
    index($0, "(" ) && index($0, s) { want=1; next }
    want && /Device:/ { match($0, /Device: [a-z0-9]+/); print substr($0, RSTART+8, RLENGTH-8); exit }'
}

# first non-Wi-Fi service that currently holds an IPv4 address
find_uplink() {
  local svc dev ip
  while IFS= read -r svc; do
    [ "$svc" = "$WIFI_SVC" ] && continue
    dev=$(dev_of "$svc"); [ -n "$dev" ] || continue
    ip=$(ipconfig getifaddr "$dev" 2>/dev/null) || continue
    [ -n "$ip" ] && { printf '%s\t%s\t%s\n' "$svc" "$dev" "$ip"; return 0; }
  done < <(networksetup -listallnetworkservices | tail -n +2 | sed 's/^\*//')
  return 1
}

default_iface() { route -n get default 2>/dev/null | awk '/interface:/{print $2}'; }

checks() {
  local d board net
  d=$(default_iface)
  [ "$d" = "$WIFI_DEV" ] && warn "default route is on Wi-Fi ($d) — internet will not work" \
                         || ok "default route on $d (not Wi-Fi)"
  board=$(curl -s --max-time 4 "http://${BOARD_IP}/" || true)
  [ -n "$board" ] && ok "board: $board" || warn "board at $BOARD_IP not answering"
  net=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 https://claude.ai || true)
  [ "$net" = "200" ] || [ "$net" = "301" ] || [ "$net" = "302" ] \
    && ok "internet reachable (HTTP $net)" || warn "no internet (HTTP ${net:-none})"
}

case "${1:-status}" in
on)
  need_root on
  up=$(find_uplink) || die "no second interface is up.
   Plug in the USB Ethernet adapter, or cable the iPhone in with Personal
   Hotspot on, then run this again. Without one, joining the board's AP
   takes the internet down with it."
  UP_SVC=$(echo "$up" | cut -f1); UP_DEV=$(echo "$up" | cut -f2); UP_IP=$(echo "$up" | cut -f3)
  ok "uplink: $UP_SVC ($UP_DEV, $UP_IP)"

  if [ ! -f "$STATE" ]; then
    networksetup -listallnetworkservices | tail -n +2 | sed 's/^\*//' > "$STATE"
    ok "saved current service order to $STATE"
  fi

  # uplink first, Wi-Fi last, everything else in between and untouched
  ordered=("$UP_SVC")
  while IFS= read -r s; do
    [ "$s" = "$UP_SVC" ] || [ "$s" = "$WIFI_SVC" ] || ordered+=("$s")
  done < "$STATE"
  ordered+=("$WIFI_SVC")
  networksetup -ordernetworkservices "${ordered[@]}" || die "could not reorder services"
  ok "service order: ${ordered[*]}"

  networksetup -setairportnetwork "$WIFI_DEV" "$AP_SSID" "$AP_PASS" \
    || die "could not join $AP_SSID — is the board powered?"
  ok "Wi-Fi joined $AP_SSID"
  networksetup -setmanual "$WIFI_SVC" "$STATIC_IP" "$STATIC_MASK" "$BOARD_IP" \
    || die "could not set the static IP"
  ok "Wi-Fi static $STATIC_IP/$STATIC_MASK"

  sleep 3; echo; checks
  echo; echo "Bridge picks the board up on its own — it polls once a second."
  ;;
off)
  need_root off
  networksetup -setdhcp "$WIFI_SVC" && ok "Wi-Fi back to DHCP"
  if [ -f "$STATE" ]; then
    mapfile -t orig < "$STATE" 2>/dev/null || while IFS= read -r l; do orig+=("$l"); done < "$STATE"
    networksetup -ordernetworkservices "${orig[@]}" && ok "service order restored"
    rm -f "$STATE"
  else
    warn "no saved order at $STATE — leaving the current one alone"
  fi
  warn "rejoin your normal Wi-Fi from the menu bar if it did not come back"
  sleep 3; echo; checks
  ;;
status)
  echo "default route  : $(default_iface)"
  echo "Wi-Fi ($WIFI_DEV)   : $(ipconfig getifaddr $WIFI_DEV 2>/dev/null || echo 'no IP')"
  if up=$(find_uplink); then echo "uplink         : $(echo "$up" | tr '\t' ' ')"
  else echo "uplink         : none up — 'on' will refuse"; fi
  echo "saved order    : $([ -f "$STATE" ] && echo yes || echo no)"
  echo; checks
  ;;
*) die "usage: $0 {on|off|status}" ;;
esac
