<?php
/** AI displacement view — rendered by [alt_ai_tracker]. */
if (!defined('ABSPATH')) exit;
?>
<div class="alt-wrap alt-ai-tracker">
    <div id="alt-ai-status" class="alt-status" role="status">Loading AI displacement data…</div>

    <div class="alt-hero" id="alt-ai-hero">
        <span class="alt-hero-value" id="alt-ai-hero-jobs">—</span>
        <span class="alt-hero-label">jobs explicitly attributed to AI, automation, or robotics</span>
        <span class="alt-hero-sub" id="alt-ai-hero-sub"></span>
    </div>

    <div class="alt-chart-grid">
        <div class="alt-chart-card alt-chart-card-wide">
            <h3>AI-attributed jobs cut per month <span class="alt-chart-sub">acceleration</span></h3>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-monthly"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <h3>Industries citing AI most <span class="alt-chart-sub">by number of layoffs</span></h3>
            <div class="alt-chart-box alt-chart-box-tall"><canvas id="alt-chart-ai-industries"></canvas></div>
        </div>
        <div class="alt-chart-card">
            <h3>In their own words <span class="alt-chart-sub">exact language from sources</span></h3>
            <div class="alt-quote-wall" id="alt-quote-wall" aria-live="polite">
                <blockquote id="alt-quote-text">—</blockquote>
                <cite id="alt-quote-cite"></cite>
            </div>
        </div>
        <div class="alt-chart-card alt-chart-card-wide">
            <h3>Companies that have explicitly cited AI</h3>
            <div class="alt-company-chips" id="alt-ai-companies"></div>
        </div>
    </div>
</div>
