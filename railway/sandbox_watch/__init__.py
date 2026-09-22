"""Checks this PUBLIC repo runs ON BEHALF OF the private sandbox repo.

Everything in here watches `dk-forge/asktherecruiter-sandbox` from outside it,
on free GitHub-hosted runners, and reaches it only through `gh api` with the
`MERGE_TRAIN_TOKEN` secret. Nothing here imports from that repo, and nothing
here is imported by the rest of this tracker.

TWO RULES FOR ANYTHING ADDED HERE.

1. The running issue stays in the SANDBOX. A check that lives here still
   opens, rewrites and closes its issue over there, so that repo's issue list
   is the one place to look for what is wrong with it.

2. A door must be PROVED before it is relied on, not assumed.
   `MERGE_TRAIN_TOKEN` is a fine-grained token and some endpoints refuse one
   whatever permissions it holds. Measured 2026-09-22 by
   `.github/workflows/sandbox-token-probe.yml`, after the owner granted
   Actions and Issues read/write:

     works   actions/workflows/<file>/runs, actions/runs?head_sha=,
             actions/runs?status=, actions/runs/<id>/jobs (with runner_id and
             steps, which NEVER_STARTED needs), commits/<branch>,
             actions/workflows, run logs, workflow enable, workflow dispatch,
             issues list/create/patch/comment/close, pull request list and
             comment, labels

     refused  commits/<sha>/check-runs      403, fine-grained PAT limitation
              commits/<sha>/status          403, same
              actions/runners               403, admin only

   The two refusals are why the sandbox's TRAIN WATCHDOG is not here: its
   first question is whether the five merge gates are green on a head SHA,
   which is exactly `check-runs` plus commit statuses. It stays in the
   sandbox. Re-run the probe before moving anything that needs those.
"""
