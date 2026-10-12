<?php
/**
 * Harness for includes/reference-data.php: drives the REAL row filter.
 *   argv[1] path to reference-data.php; stdin {"doc":..., "params":...}
 * Prints the filtered document as JSON.
 */
error_reporting(E_ALL & ~E_DEPRECATED);
define('ABSPATH', '/tmp/');
function add_action($tag, $fn, $prio = 10, $args = 1) {}
require $argv[1];
$in = json_decode(stream_get_contents(STDIN), true);
echo json_encode(alt_reference_filter($in['doc'], $in['params']));
