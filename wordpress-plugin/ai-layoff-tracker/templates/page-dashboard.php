<?php
/** Dashboard charts — rendered by [alt_dashboard]. */
if (!defined('ABSPATH')) exit;
?>
<div class="alt-wrap alt-dashboard">
    <div id="alt-dashboard-status" class="alt-status" role="status">Loading charts…</div>

    <div class="alt-chart-grid">
        <div class="alt-chart-card alt-chart-card-wide">
            <div class="alt-chart-h">Jobs cut per month <span class="alt-chart-sub">full history</span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Where the cuts are <span class="alt-chart-sub">by industry · <span class="alt-ai-key"></span> AI-attributed share</span></div>
            </div>
            <div class="alt-barlist" id="alt-bars-industries"></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">jobs by reason tag</span></div>
            <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-reasons"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Where the cuts are <span class="alt-chart-sub">by US state · <span class="alt-ai-key"></span> AI-attributed share</span></div>
            </div>
            <div class="alt-barlist" id="alt-bars-states"></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Where the cuts are <span class="alt-chart-sub">by country · <span class="alt-ai-key"></span> AI-attributed share</span></div>
            </div>
            <div class="alt-barlist" id="alt-bars-countries"></div>
        </div>
        <div class="alt-chart-card alt-chart-card-wide">
            <div class="alt-chart-h">Cumulative AI-attributed job losses <span class="alt-chart-sub">acceleration curve</span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-cumulative"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <div class="alt-chart-h">Largest single job cuts <span class="alt-chart-sub">all time</span></div>
            <div id="alt-leaderboard" class="alt-leaderboard"></div>
        </div>
    </div>
</div>
