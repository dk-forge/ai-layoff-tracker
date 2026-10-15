<?php
/**
 * The account emails (signup confirmation, change confirmation, welcome) in
 * the subscriber design the owner approved on 2026-09-29.
 *
 * Until 2.20.246 these three were plain text while the nine digest editions
 * wore the new design, so the first two emails a reader ever got looked like a
 * different sender. This file gives them the same shell as the relay's
 * railway/digest_layout.py: grey page, white 600px card that is fluid on a
 * phone, bold heading, a red accent bar for the AI Layoff Tracker brand, one
 * button, and the CAN-SPAM postal address at the foot.
 *
 * DARK MODE. Like the relay, there is no prefers-color-scheme block (most
 * clients ignore it and the ones that honour it strip it on forward). Every
 * colour here is one the relay already uses and that clears 4.5:1 on its
 * background BOTH upright and once a dark-mode client inverts it;
 * railway/tests/test_account_mail.py checks that.
 *
 * NO IMAGES AND NOTHING FETCHED: the brand is text, the button is a table
 * cell. The plain-text part is still the old body word for word, so the
 * existing body tests keep pinning the wording.
 *
 * Loaded guarded (is_readable) from the main plugin file; every caller checks
 * function_exists() and falls back to the old plain-text wp_mail.
 */

if (!defined('ABSPATH') && !defined('ALT_ACCOUNT_MAIL_TEST')) {
    exit;
}

/** The palette, shared with railway/digest_layout.py + digest_design.py. */
function alt_account_mail_palette() {
    return array(
        'page'   => '#eef1f5',
        'card'   => '#ffffff',
        'ink'    => '#15181d',
        'muted'  => '#454950',
        'link'   => '#0b4f9c',
        'accent' => '#b42a18',
        'rule'   => '#e4e7ec',
        'button' => '#0b4f9c',
        'on_button' => '#ffffff',
    );
}

function alt_account_mail_esc($s) {
    return htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/**
 * Turn a plain-text body into paragraphs. A bare URL line that is the button's
 * URL is replaced by the button, in place; with no such line the button goes
 * last. "  - item" runs become a list.
 */
function alt_account_mail_paragraphs($text, $button_url, $button_html = '') {
    $c = alt_account_mail_palette();
    $font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
    $p_style = "margin:0 0 16px;font-family:$font;font-size:16px;line-height:1.55;color:{$c['ink']};";
    $out = '';
    foreach (preg_split("/\n{2,}/", trim((string) $text)) as $chunk) {
        $chunk = trim($chunk, "\n");
        if ($chunk === '') continue;
        if ($button_url !== '' && trim($chunk) === $button_url) { $out .= $button_html; $button_html = ''; continue; }
        // The postal address is the footer's job; never print it twice.
        if (strpos($chunk, 'AskTheRecruiter, Netherlands') !== false) continue;
        $lines = explode("\n", $chunk);
        // "Lead-in:\n<button url>": keep the lead-in, the button follows it.
        $here = '';
        if ($button_url !== '' && count($lines) > 1 && trim(end($lines)) === $button_url) {
            array_pop($lines);
            $here = $button_html;
            $button_html = '';
        }
        $items = array();
        $lead = array();
        foreach ($lines as $line) {
            if (preg_match('/^\s*-\s+(.*)$/', $line, $m)) $items[] = $m[1];
            else $lead[] = trim($line);
        }
        $lead_txt = trim(implode(' ', $lead));
        if ($lead_txt !== '') {
            $html = alt_account_mail_esc($lead_txt);
            // A URL inside a sentence stays a link (never a bare unclickable string).
            $html = preg_replace('#(https?://[^\s<]+)#', '<a href="$1" style="color:'
                . $c['link'] . ';text-decoration:underline;font-weight:600;word-break:break-all;">$1</a>', $html);
            $out .= '<p style="' . $p_style . '">' . $html . '</p>';
        }
        if ($items) {
            $out .= '<ul style="margin:0 0 16px;padding-left:22px;font-family:' . $font
                  . ';font-size:16px;line-height:1.55;color:' . $c['ink'] . ';">';
            foreach ($items as $it) $out .= '<li style="margin:0 0 4px;">' . alt_account_mail_esc($it) . '</li>';
            $out .= '</ul>';
        }
        $out .= $here;
    }
    return $out . $button_html;
}

/**
 * The full HTML document.
 *
 * $footer_links: list of array(label, url); empty urls are skipped. The postal
 * address is UNCONDITIONAL, like the digest footer block.
 */
function alt_account_mail_html($heading, $text, $button_url, $button_label, $footer_links = array(), $preheader = '') {
    $c = alt_account_mail_palette();
    $font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
    $e = 'alt_account_mail_esc';
    $hidden = $preheader === '' ? '' :
        '<div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;'
        . 'font-size:1px;line-height:1px;mso-hide:all;">' . $e($preheader) . '</div>';
    $button = '';
    if ($button_url !== '') {
        $button = '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px;">'
            . '<tr><td bgcolor="' . $c['button'] . '" style="border-radius:6px;background-color:' . $c['button'] . ';">'
            . '<a href="' . $e($button_url) . '" style="display:inline-block;padding:14px 24px;font-family:' . $font
            . ';font-size:16px;line-height:1.2;font-weight:700;color:' . $c['on_button']
            . ';text-decoration:none;border-radius:6px;">' . $e($button_label) . '</a></td></tr></table>'
            . '<p style="margin:0 0 16px;font-family:' . $font . ';font-size:14px;line-height:1.5;color:' . $c['muted']
            . ';">If the button does not work, paste this link into your browser:<br>'
            . '<a href="' . $e($button_url) . '" style="color:' . $c['link'] . ';text-decoration:underline;word-break:break-all;">'
            . $e($button_url) . '</a></p>';
    }
    $links = array();
    foreach ($footer_links as $l) {
        if (!is_array($l) || empty($l[1])) continue;
        $links[] = '<a href="' . $e($l[1]) . '" style="color:' . $c['link'] . ';text-decoration:underline;">' . $e($l[0]) . '</a>';
    }
    $small = 'margin:0 0 8px;font-family:' . $font . ';font-size:13px;line-height:1.6;color:' . $c['muted'] . ';';
    $footer = ($links ? '<p style="' . $small . '">' . implode(' &middot; ', $links) . '</p>' : '')
            . '<p style="' . $small . '">AskTheRecruiter, Netherlands.</p>';

    return '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<title>' . $e($heading) . '</title></head>'
        . '<body style="margin:0;padding:0;background-color:' . $c['page'] . ';">' . $hidden
        . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="' . $c['page']
        . '" style="background-color:' . $c['page'] . ';"><tr><td align="center" style="padding:24px 12px;">'
        . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        . 'style="width:100%;max-width:600px;"><tr><td bgcolor="' . $c['card'] . '" style="padding:28px 24px;'
        . 'background-color:' . $c['card'] . ';border-radius:8px;">'
        . '<p style="margin:0 0 20px;padding-left:12px;border-left:4px solid ' . $c['accent'] . ';font-family:' . $font
        . ';font-size:14px;line-height:1.4;font-weight:800;letter-spacing:0.02em;color:' . $c['ink'] . ';">AskTheRecruiter.com</p>'
        . '<h1 style="margin:0 0 16px;font-family:' . $font . ';font-size:24px;line-height:1.25;font-weight:800;'
        . 'letter-spacing:-0.01em;color:' . $c['ink'] . ';">' . $e($heading) . '</h1>'
        . alt_account_mail_paragraphs($text, $button_url, $button)
        . '<hr style="border:none;border-top:1px solid ' . $c['rule'] . ';margin:24px 0 16px;">'
        . $footer
        . '</td></tr></table></td></tr></table></body></html>';
}

/** Confirmation (first signup or change): one button, no unsubscribe link (2026-08-17 decision). */
function alt_account_mail_confirm_html($body_text, $confirm_url, $is_change) {
    // The body's first line is the old plain text; the button replaces the bare URL.
    $heading = $is_change ? 'Confirm your change' : 'Confirm your subscription';
    $label = $is_change ? 'Apply the change' : 'Confirm my subscription';
    // NO unsubscribe or preferences link: a scanner that follows every link in
    // a confirmation would confirm and then unsubscribe a person who was not
    // there (subscribe.php, 2026-08-17). The List-Unsubscribe header remains.
    return alt_account_mail_html($heading, $body_text, $confirm_url, $label, array(),
        'Nothing is sent until you confirm.');
}

/** Welcome: preferences + unsubscribe links in the footer. */
function alt_account_mail_welcome_html($body_text, $prefs_url, $unsub_url) {
    return alt_account_mail_html("You're subscribed", $body_text, $prefs_url, 'Open my preferences',
        array(array('Manage preferences', $prefs_url), array('Unsubscribe', $unsub_url)),
        'Your lists and when the first edition arrives.');
}
