# Host acceptance after READY: 0102

Use the dedicated test nodes. Keep the existing installed swap flow available.
The candidate XBT node can update privkeyio :1 in place; BTC and controller require
fresh installations. Verify installer SHA256SUMS before transfer/install.

1. On the XBT test node, record node identity, original channel funding and UI
   password before updating. Update normally on the same volume; verify the same
   identity, CHANNELD_NORMAL, same funding, synchronization, UI login and a small
   ordinary payment. Do not restore a backup as an update method.
2. Install the dedicated BTC candidate, attach its synced unpruned BTC backend,
   and verify native node/UI readiness. Establish test channel liquidity.
3. On both coordinators run Enable Swap Coordinator, explicitly confirm, and
   restart normally. Review and confirm incoming/outgoing bounded grants, then
   show each bounded controller credential. This never requires entering SCIDs.
4. On the fresh controller complete Initialize Swap Service while stopped. Start
   it. Pair each direction with the incoming/outgoing HTTPS CLNrest URL, StartOS
   root CA and correct bounded credentials. Inspect status and remaining limits.
5. Use a fresh recipient invoice with enough lifetime, final CLTV <=40 and private
   hints if needed. Review both amounts and the Neoxa price/markup (default 0%).
   Confirm that exact review. Pay the published incoming invoice once. Verify
   paid/settled at the recipient and in controller history. Repeat in the reverse
   direction only after the first is terminal.

A lost reply is not permission to pay again or recreate a journal. Inspect saved
status/history. New quotes refuse if Neoxa pricing or a bounded route is unavailable.
Ordinary worker recovery uses its saved price and exact attempt.

Host acceptance, real-network liquidity/routes and live Neoxa availability are
not asserted by the regtest build receipt. Report the first failed step and its
sanitized error; do not post runes, private invoices, seeds or complete databases.
