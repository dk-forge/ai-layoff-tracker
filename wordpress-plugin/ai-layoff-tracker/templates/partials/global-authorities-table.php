<?php if (!defined('ABSPATH')) exit; ?>
<?php
/**
 * Global layoff authorities reference. Transparency table: for each country,
 * its official labour authority, whether it publishes PUBLIC per-employer layoff
 * notices, and how we track layoffs there. Required by templates/page-sources.php.
 * Ground truth: only Quebec (Canada) and US states publish public per-employer
 * notices; every other country's filings are confidential (aggregate stats only).
 */
$alt_authorities = array(
  'North America' => array(
    array('Canada (Quebec)', 'MESS (Ministère de l\'Emploi)', 'https://www.quebec.ca/gouvernement/ministeres-organismes/emploi-solidarite-sociale/coordonnees-structure/generales/avis-licenciement-collectif', '✅ Public registry', 'Direct, we parse the public registry (data live)'),
    array('Canada (Ontario)', 'Ministry of Labour', 'https://www.ontario.ca', '❌ Confidential filing', 'Reviewed national news outlets (data live)'),
    array('Canada (British Columbia)', 'Ministry of Labour', 'https://www2.gov.bc.ca', '❌ Confidential filing', 'Reviewed national news outlets (data live)'),
    array('Canada (Alberta)', 'Ministry of Jobs', 'https://www.alberta.ca', '❌ Confidential filing', 'Reviewed national news outlets (data live)'),
    array('Canada (Federal)', 'Employment and Social Development Canada', 'https://www.canada.ca', '❌ Confidential filing', 'Reviewed national news outlets (data live)'),
  ),
  'Europe' => array(
    array('Austria', 'Arbeitsmarktservice (AMS)', 'https://www.ams.at', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Belgium', 'FPS Employment', 'https://employment.belgium.be', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Bulgaria', 'Employment Agency', 'https://www.az.government.bg', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Croatia', 'Croatian Employment Service (HZZ)', 'https://www.hzz.hr', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Cyprus', 'Ministry of Labour', 'https://www.gov.cy', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Czechia', 'Labour Office', 'https://www.uradprace.cz', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Denmark', 'STAR / regional authorities', 'https://star.dk', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Estonia', 'Unemployment Insurance Fund', 'https://www.tootukassa.ee', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Finland', 'Ministry of Economic Affairs & Employment', 'https://tem.fi', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('France', 'Ministry of Labour / DREETS (PSE)', 'https://travail-emploi.gouv.fr', '⚠️ Partial (large events only)', 'Eurofound ERM + reviewed news (data live)'),
    array('Germany', 'Federal Employment Agency', 'https://www.arbeitsagentur.de', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Greece', 'Ministry of Labour', 'https://ypergasias.gov.gr', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Hungary', 'Government Employment Service', 'https://kormany.hu', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Ireland', 'Workplace Relations Commission', 'https://www.workplacerelations.ie', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Italy', 'Ministry of Labour', 'https://www.lavoro.gov.it', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Latvia', 'State Employment Agency', 'https://www.nva.gov.lv', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Lithuania', 'Employment Service', 'https://uzt.lt', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Luxembourg', 'Ministry of Labour', 'https://guichet.public.lu', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Malta', 'Jobsplus', 'https://jobsplus.gov.mt', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Netherlands', 'UWV', 'https://www.uwv.nl', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Norway', 'NAV', 'https://www.nav.no', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('Poland', 'Voivodeship labour offices (WUP); Mazowieckie publishes employers by name', 'https://wupwarszawa.praca.gov.pl/urzad/dla-mediow', '✅ Mazovia: public named register (rest: aggregate/confidential)', 'WUP Warszawa register imported directly; other regions via ERM + reviewed news'),
    array('Portugal', 'ACT', 'https://www.act.gov.pt', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Romania', 'National Employment Agency (ANOFM)', 'https://www.anofm.ro', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Slovakia', 'Central Office of Labour', 'https://www.upsvr.gov.sk', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Slovenia', 'Employment Service', 'https://www.ess.gov.si', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Spain', 'Ministry of Labour (ERE)', 'https://www.mites.gob.es', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Sweden', 'Arbetsförmedlingen', 'https://arbetsformedlingen.se', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
    array('Switzerland', 'SECO', 'https://www.seco.admin.ch', '❌ Confidential filing', 'Eurofound ERM + reviewed news'),
    array('United Kingdom', 'Insolvency Service / DBT (HR1)', 'https://www.gov.uk', '❌ Confidential filing', 'Eurofound ERM + reviewed news (data live)'),
  ),
  'Asia-Pacific' => array(
    array('China', 'MOHRSS', 'https://www.mohrss.gov.cn', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Hong Kong', 'Labour Department', 'https://www.labour.gov.hk', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('India', 'Ministry of Labour & Employment', 'https://labour.gov.in', '❌ Confidential filing', 'Reviewed national news outlets (data live)'),
    array('Indonesia', 'Ministry of Manpower', 'https://kemnaker.go.id', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Japan', 'MHLW', 'https://www.mhlw.go.jp', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Malaysia', 'Ministry of Human Resources', 'https://www.mohr.gov.my', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Philippines', 'DOLE', 'https://www.dole.gov.ph', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Singapore', 'Ministry of Manpower', 'https://www.mom.gov.sg', '⚠️ Partial (large events only)', 'Reviewed national news outlets'),
    array('South Korea', 'Ministry of Employment & Labor', 'https://www.moel.go.kr', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Taiwan', 'Ministry of Labor', 'https://www.mol.gov.tw', '⚠️ Partial (large events only)', 'Reviewed national news outlets'),
    array('Thailand', 'Ministry of Labour', 'https://www.mol.go.th', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Vietnam', 'MOLISA', 'https://www.molisa.gov.vn', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Australia', 'Fair Work Ombudsman', 'https://www.fairwork.gov.au', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('New Zealand', 'MBIE', 'https://www.mbie.govt.nz', '❌ Confidential filing', 'Reviewed national news outlets'),
  ),
  'Middle East' => array(
    array('Israel', 'Ministry of Labor', 'https://www.gov.il', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Saudi Arabia', 'Ministry of Human Resources', 'https://hrsd.gov.sa', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('United Arab Emirates', 'MOHRE', 'https://www.mohre.gov.ae', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Qatar', 'Ministry of Labour', 'https://www.mol.gov.qa', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Turkey', 'Ministry of Labour & Social Security', 'https://www.csgb.gov.tr', '❌ Confidential filing', 'Reviewed national news outlets'),
  ),
  'Africa' => array(
    array('Egypt', 'Ministry of Labour', 'https://www.manpower.gov.eg', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Kenya', 'Ministry of Labour', 'https://labour.go.ke', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Nigeria', 'Federal Ministry of Labour', 'https://labour.gov.ng', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('South Africa', 'Department of Employment & Labour', 'https://www.labour.gov.za', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Morocco', 'Ministry of Employment', 'https://www.emploi.gov.ma', '❌ Confidential filing', 'Reviewed national news outlets'),
  ),
  'Latin America' => array(
    array('Argentina', 'Ministry of Labour', 'https://www.argentina.gob.ar/trabajo', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Brazil', 'Ministry of Labour & Employment', 'https://www.gov.br/trabalho-e-emprego', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Chile', 'Directorate of Labour', 'https://www.dt.gob.cl', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Colombia', 'Ministry of Labour', 'https://www.mintrabajo.gov.co', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Mexico', 'Secretariat of Labor (STPS)', 'https://www.gob.mx/stps', '❌ Confidential filing', 'Reviewed national news outlets'),
    array('Peru', 'Ministry of Labour', 'https://www.gob.pe/mtpe', '❌ Confidential filing', 'Reviewed national news outlets'),
  ),
);
$alt_auth_count = 0; foreach ($alt_authorities as $alt_reg_rows) { $alt_auth_count += count($alt_reg_rows); }
?>
<details class="alt-health-section" open>
  <summary><b>Every country's labour authority, and how we track it (<?php echo (int) $alt_auth_count; ?> countries)</b></summary>
  <p class="alt-auth-note">Only Quebec (Canada) and US states publish public per-employer layoff notices. Everywhere else the filing is confidential and only aggregate statistics are released, so we rely on Eurofound ERM plus reviewed news across the EU and EEA, and reviewed national news outlets elsewhere.</p>
  <?php foreach ($alt_authorities as $alt_region => $alt_rows): ?>
  <h3><?php echo esc_html($alt_region); ?></h3>
  <div class="alt-health-table-wrap">
  <table class="alt-sortable">
    <thead><tr><th>Country</th><th>Official labour authority</th><th>Public per-employer notices?</th><th data-nosort>How we track it</th></tr></thead>
    <tbody>
    <?php foreach ($alt_rows as $alt_row): list($alt_country, $alt_authority, $alt_url, $alt_pub, $alt_track) = $alt_row; ?>
      <tr>
        <th><?php echo esc_html($alt_country); ?></th>
        <td><a href="<?php echo esc_url($alt_url); ?>" target="_blank" rel="noopener"><?php echo esc_html($alt_authority); ?> &#8599;</a></td>
        <td><?php echo esc_html($alt_pub); ?></td>
        <td><?php echo esc_html($alt_track); ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  </div>
  <?php endforeach; ?>
</details>
