<?php
/** Dashboard charts — rendered by [alt_dashboard]. */
if (!defined('ABSPATH')) exit;
?>
<div class="alt-wrap alt-dashboard">
    <div id="alt-dashboard-status" class="alt-status" role="status">Loading charts…</div>

    <div class="alt-chart-grid">
        <div class="alt-chart-card alt-chart-card-wide">
            <div class="alt-chart-h">Jobs cut per week <span class="alt-chart-sub">rolling 52 weeks</span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Top 10 industries <span class="alt-chart-sub">by total job losses</span></div>
            <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-industries"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">jobs by reason tag</span></div>
            <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-reasons"></canvas></div>
        </div>
        <div class="alt-chart-card alt-chart-card-wide">
            <div class="alt-chart-h">Cumulative AI-attributed job losses <span class="alt-chart-sub">acceleration curve</span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-cumulative"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Top 10 countries <span class="alt-chart-sub">by total job losses</span></div>
            <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-countries"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Largest single events <span class="alt-chart-sub">all time</span></div>
            <div id="alt-leaderboard" class="alt-leaderboard"></div>
        </div>
    </div>
</div>
