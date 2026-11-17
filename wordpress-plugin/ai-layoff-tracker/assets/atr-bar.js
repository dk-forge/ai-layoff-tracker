/* Phone sign-up bar on the employer pages (includes/atr-signup-cta.php). */
(function(){
  var k='alt_atr_bar_closed',bar=document.getElementById('alt-atr-bar');
  if(!bar)return;
  var closed=false;
  try{closed=window.localStorage.getItem(k)==='1';}catch(e){}
  if(closed)return;
  bar.hidden=false;document.body.classList.add('alt-atr-bar-on');
  document.getElementById('alt-atr-bar-close').addEventListener('click',function(){
    bar.hidden=true;document.body.classList.remove('alt-atr-bar-on');
    try{window.localStorage.setItem(k,'1');}catch(e){}
  });
})();
