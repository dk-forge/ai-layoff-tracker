<?php
define('ABSPATH', '/');
function add_action(...$a) {} function add_filter(...$a) {} function register_rest_route(...$a) {}
function alt_digest_list_names() { return array('layoffs' => 'AI layoffs'); }
function alt_digest_lists() { return array('layoffs' => array('consent' => 'c', 'freq' => 'f')); }
function alt_digest_valid_freq($f) { return $f; }
function alt_mail_postal_address() { return 'AskTheRecruiter, Netherlands.'; }
require $argv[1];
echo alt_welcome_body(array('c' => 1, 'f' => 'weekly'), 'https://x/prefs', 'https://x/unsub/abc');
