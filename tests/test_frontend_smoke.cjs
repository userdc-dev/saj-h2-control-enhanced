/* Minimal, dependency-free dynamic card smoke test in Node.
 * Exercises actual card methods and interaction handlers without HA/inverter,
 * a real browser, or remote network calls. Not a replacement for browser QA.
 */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

class MockNode {
  constructor(tag){
    this.tagName=tag.toLowerCase();
    this.children=[];
    this.parentElement=null;
    this.attributes={};
    this.listeners={};
    this.style={};
    this.className="";
    this.value="";
    this.open=false;
    this.disabled=false;
    this.tabIndex=-1;
    this._text="";
  }
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(c=>c.textContent||"").join("");}
  append(...items){
    for(const item of items){
      const child=typeof item==="string"?new MockNode("text"):item;
      if(typeof item==="string")child._text=item;
      child.parentElement=this;
      this.children.push(child);
    }
  }
  replaceChildren(...items){this._text="";this.children=[];this.append(...items);}
  setAttribute(name,value){this.attributes[name]=String(value);if(name==="class")this.className=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
  addEventListener(type,callback){this.listeners[type]=callback;}
  querySelector(selector){
    const selectorMatch=node=>selector==="input"?node.tagName==="input":
      selector.startsWith(".")?node.className.split(" ").includes(selector.slice(1)):
      node.tagName===selector;
    for(const node of this.walk())if(selectorMatch(node))return node;
    return null;
  }
  *walk(){for(const n of this.children){yield n;yield* n.walk();}}
  getBoundingClientRect(){return {left:0,width:920,height:300};}
  select(){this._selectedText=this.value;}
  focus(){}
}
class MockHTMLElement extends MockNode {
  constructor(){super("custom-card");}
  attachShadow(){this.shadowRoot=new MockNode("shadow-root");return this.shadowRoot;}
}
const registry=new Map();
const copied=[];
const globals={
  document:{
    createElement:tag=>new MockNode(tag),
    createElementNS:(_ns,tag)=>new MockNode(tag),
    execCommand:()=>true
  },
  customElements:{get:name=>registry.get(name),define:(name,ctor)=>registry.set(name,ctor)},
  window:{customCards:[]},
  navigator:{clipboard:{writeText:async value=>{copied.push(value);}}},
  HTMLElement:MockHTMLElement,
  Intl,Date,Promise,Math,Map,Set,Number,Object,String,JSON,
  console,
};
const js=fs.readFileSync(path.resolve(__dirname,"../custom_components/saj_h2_control_enhanced/frontend/saj-tou-dynamic-card.js"),"utf8");
vm.runInNewContext(js,globals,{filename:"saj-tou-dynamic-card.js"});
const Card=registry.get("saj-tou-dynamic-card");
assert.ok(Card,"custom element registered");
const card=new Card();
const roles=[
  ["grid_signed_power","sensor.home_grid_signed_power","Grid power signed"],
  ["grid_import_power","sensor.home_grid_import_power","Power imported"],
  ["grid_export_power","sensor.home_grid_export_power","Power exported"],
  ["battery_charged_energy","sensor.home_battery_energy_charged","Energy charged"],
  ["battery_discharged_energy","sensor.home_battery_energy_discharged","Energy discharged"],
  ["battery_state_of_charge","sensor.home_battery_soc","Battery state of charge"],
  ["solar_production_energy","sensor.home_solar_kwh","Solar total"],
  ["solar_production_power","sensor.home_solar_w","Solar watts"],
  ["grid_import_energy_estimate","sensor.home_import_kwh","Grid import energy"],
  ["grid_export_energy_estimate","sensor.home_export_kwh","Grid export energy"]
];
const states={};
for(const [role,id,name] of roles){
  states[id]={entity_id:id,state:"1",attributes:{friendly_name:name,saj_energy_role:role}};
}
const forecastId="sensor.owner_editable_solar_forecast";
states[forecastId]={
  entity_id:forecastId,state:"75",last_updated:new Date().toISOString(),
  attributes:{
    friendly_name:"Editable solar forecast",saj_tou_role:"editable_forecast",
    today:75,remaining_today:35,tomorrow:80,week:500,
    daily:Array.from({length:7},(_,i)=>({
      date:new Date(Date.now()+i*86400000).toISOString().slice(0,10),
      kwh:75+i,
    })),
    hourly_today:Array.from({length:24},(_,i)=>({
      hour:String(i).padStart(2,"0")+":00",kwh:i>6&&i<19?4:0,cloud:25
    })),
    settings:{
      configured:true,
      groups:[{count:9,watts:440,azimuth:29,tilt:25},
              {count:15,watts:440,azimuth:27,tilt:25},
              {count:6,watts:440,azimuth:299,tilt:25}],
      efficiency:87,ac_limit_kw:10
    },learning:{status:"Calibrating",clear_sky_hours:2}
  }
};
states["sensor.owner_cost_estimate"]={
  entity_id:"sensor.owner_cost_estimate",state:"1.51",
  attributes:{
    saj_tou_role:"cost_estimate",
    pricing:{
      configured:true,currency:"AUD",
      tariff_profile:{
        configured:true,version:1,import_bands:[],
        default_import_rate:.35,export_standard_rate:.05,export_fallback_rate:.05,
        export_high_rate:.3,export_high_windows:[],export_standard_windows:[],
        daily_supply:1.5,gst_percent:10,gst_mode:"included",
        gst_on_import:true,gst_on_export:false,gst_on_supply:true,
        other_tax_percent:0,other_tax_on_import:true,other_tax_on_export:false,
        other_tax_on_supply:true,high_fit_eligibility:"battery_only_unverified"
      }
    },
    today:{net_cost:1.51,import_kwh:.03,export_kwh:.2,
           import_cost:.01,export_credit:.01,supply_cost:1.5,
           supply_days_charged:1,coverage_seconds:3600,tariff_coverage_seconds:3600,
           self_supply_estimated_benefit:0.4,battery_discharge_illustrative_value:0.3,
           import_bands:[],export_bands:[]},
    month:{net_cost:1.51,import_kwh:.03,export_kwh:.2,
           import_cost:.01,export_credit:.01,supply_cost:1.5,
           supply_days_charged:1,coverage_seconds:3600,tariff_coverage_seconds:3600,
           self_supply_estimated_benefit:0.4,battery_discharge_illustrative_value:0.3,
           import_bands:[],export_bands:[]}
  }
};
// Daily read-only inverter kWh counters are not power (W) and should
// remain separate from the gap-aware derived grid import/export totals.
for(const [key,value] of Object.entries({
  solar_today:15.26,home_today:4.86,
  battery_charge_today:9.86,battery_discharge_today:0.42
})){
  const id="sensor.saj_h2_safe_monitor_"+key;
  states[id]={entity_id:id,state:String(value),
    attributes:{friendly_name:"SAJ H2 Safe Monitor "+key,
                unit_of_measurement:"kWh"}};
}
for(const [key,value] of Object.entries({
  solar:12410,home:2980,battery:-9440,soc:99,
  stored:39.60,gridImport:0,gridExport:0,
  outlook:78.36,remaining:15.32,tomorrow:94.34
})){
  const ids={
    solar:"total_solar_power",
    home:"home_consumption",
    battery:"battery_power",soc:"battery_state_of_charge",
    stored:"estimated_battery_energy",
    gridImport:"grid_import_direction_unverified",
    gridExport:"grid_export_direction_unverified",
    outlook:"today_s_solar_outlook_actual_remaining",
    remaining:"solar_forecast_remaining_today",
    tomorrow:"tomorrow_s_solar_forecast"
  };
  const id="sensor.saj_h2_safe_monitor_"+ids[key];
  states[id]={entity_id:id,state:String(value),attributes:{}};
}
card._hass={states,config:{currency:"AUD"},callApi:async()=>[]};

const find=(root,className)=>[root,...root.walk()]
  .find(n=>n.className.split(" ").includes(className));
const findAll=(root,tag)=>[root,...root.walk()].filter(n=>n.tagName===tag);

async function main(){
  const guide=card._energySetupGuide();
  assert.equal(guide.tagName,"details");
  assert.equal(guide.open,false,"sensor guide must start collapsed");
  assert.equal(findAll(guide,"section").length,4,"4 compact sensor groups");
  assert.ok(guide.textContent.includes("Energy charged"));
  assert.ok(guide.textContent.includes("Energy discharged"));
  assert.ok(guide.textContent.includes("Grid · Electricity"));
  const inputs=findAll(guide,"input");
  assert.ok(inputs.some(input=>input.value==="sensor.home_battery_energy_charged"));
  assert.ok(inputs.some(input=>input.value==="sensor.home_battery_energy_discharged"));
  const row=inputs.find(input=>input.value==="sensor.home_grid_signed_power").parentElement;
  const copyButton=row.children.find(node=>node.tagName==="button");
  assert.ok(copyButton&&!copyButton.disabled,"copy button enabled for discovered ID");
  copyButton.listeners.click();
  await Promise.resolve();
  assert.deepEqual(copied,["sensor.home_grid_signed_power"]);
  row.children[0].listeners.click();
  assert.equal(row.children[0]._selectedText,"sensor.home_grid_signed_power");

  const originalHistoryChart=card._historyChart.bind(card);
  card._historyChart=()=>new MockNode("div");
  const energy=card._energyOverview();
  const daily=find(energy,"flowDailyTotals");
  assert.ok(daily,"Live energy includes a daily cumulative row");
  assert.equal(daily.children.length,5,"five cells align with five power columns");
  assert.ok(daily.children[0].textContent.includes("15.26 kWh"));
  assert.ok(daily.children[1].textContent.includes("4.86 kWh"));
  assert.ok(daily.children[2].textContent.includes("9.86 kWh"));
  assert.ok(daily.children[2].textContent.includes("0.42 kWh"));
  assert.ok(daily.children[3].textContent.includes("0.03 kWh"));
  assert.ok(daily.children[3].textContent.includes("0.20 kWh"));
  assert.ok(daily.children[4].textContent.includes("40.00 kWh"),
    "forecast-by-now is today's forecast minus remaining, NOT actual solar");
  assert.ok(energy.textContent.includes("0 W")||energy.textContent.includes("0 W"),
    "live power values remain in W independently of kWh row");
  delete states["sensor.saj_h2_safe_monitor_battery_discharge_today"];
  const absent=card._energyOverview();
  assert.ok(find(absent,"flowDailyTotals").children[2].textContent.includes("—"),
    "missing energy sensor must not be silently shown as zero");
  states["sensor.saj_h2_safe_monitor_battery_discharge_today"]={
    entity_id:"sensor.saj_h2_safe_monitor_battery_discharge_today",
    state:"0.42",attributes:{unit_of_measurement:"kWh"}};
    card._historyChart=originalHistoryChart;
  card._historyHours=1/6;
  card._historyData={
    solar:[{t:Date.now()-120000,y:3200},{t:Date.now()-60000,y:4200}],
    home:[{t:Date.now()-120000,y:1500},{t:Date.now()-60000,y:1100}],
    battery:[{t:Date.now()-120000,y:-800},{t:Date.now()-60000,y:-3000}],
    gridImport:[],gridExport:[]
  };
  const shortChart=card._historyChart();
  assert.ok(findAll(shortChart,"option").some(o=>o.textContent==="10 minutes"),
    "Historic Data dropdown offers a 10-minute window");
  assert.equal(findAll(shortChart,"option")[0].value,String(1/6),
    "shortest window comes before six hours");
  assert.ok(shortChart.textContent.includes("30-second steps"),
    "10-minute chart uses a precise 30-second hover cursor");
  assert.ok(find(shortChart,"historySvg").listeners.pointermove,
    "10-minute graph is mouse-hoverable");

  // Regression: exported power is negative on the purple graph even if
  // Recorder has NO matching event from the zero-valued import sensor.
  // Hover must display that exact export sample, not "no nearby reading".
  const hoverTarget=Date.now()-65000;
  const makeSample=(w,t=hoverTarget)=>({t,y:w});
  const probeGrid=(imports,exports,offsetMs=0)=>{
    card._historyData={
      solar:[makeSample(9000)],home:[],battery:[],
      gridImport:imports,gridExport:exports
    };
    const rendered=card._historyChart();
    const plot=find(rendered,"historySvg");
    const hoverEpoch=hoverTarget+offsetMs;
    const fraction=(hoverEpoch-(Date.now()-600000))/600000;
    const svgX=63+fraction*(938-63);
    plot.listeners.pointermove({clientX:svgX*920/960});
    return {text:find(rendered,"historyTooltip").textContent,
      svg:plot};
  };
  const exportOnly=probeGrid([],[
    makeSample(6700,hoverTarget-20000),makeSample(6760)
  ]);
  assert.match(exportOnly.text,/Grid ±: -6\.76 kW · exporting/,
    "grid tooltip must show negative export when import has no nearby sample");
  assert.ok(exportOnly.text.includes("grid:")&&
    !exportOnly.text.includes("Grid ±: — no nearby reading"),
    "export-only reading must include the actual sample time");
  const importOnly=probeGrid([makeSample(3250)],[]);
  assert.match(importOnly.text,/Grid ±: 3\.25 kW · importing/,
    "grid tooltip must show positive import when export has no nearby sample");
  const combined=probeGrid([makeSample(1000)],[makeSample(2500)]);
  assert.match(combined.text,/Grid ±: -1\.50 kW · exporting/,
    "synchronous import and export readings should retain signed net flow");
  const idle=probeGrid([makeSample(0)],[]);
  assert.match(idle.text,/Grid ±: 0\.00 kW · no net exchange/,
    "a genuine zero must be distinguished from missing history");
  const absentGrid=probeGrid([],[]);
  assert.match(absentGrid.text,/Grid ±: — no nearby reading/,
    "only absent import AND export readings should yield a missing-value dash");

  card._historyHours=24;
  card._historyData=null;
  const costs=card._costPage();
  assert.equal(find(costs,"costEditorShell").open,false,
    "already configured tariff editor should be folded away");
  assert.equal(find(costs,"costBreakdown").open,false,
    "cost breakdown should start collapsed");
  assert.ok(costs.textContent.includes("Edit electricity tariffs"));
  const today=new Date();today.setHours(0,0,0,0);
  card._forecastHistoryDate=today.toLocaleDateString("en-CA");
  card._forecastHistoryFetchedAt=Date.now();
  card._forecastHistoryData=[
    {t:today.getTime()+8*3600000,y:1500},
    {t:today.getTime()+8*3600000+10*60000,y:2000}
  ];
  const forecast=card._forecastPage();
  const chart=find(forecast,"actualForecast");
  assert.ok(chart,"actual/projected chart appears");
  const svg=find(chart,"forecastSvg");
  assert.ok(svg?.listeners.pointermove&&svg.listeners.pointerdown&&
    svg.listeners.keydown,"forecast SVG supports hover tap and keyboard");
  svg.listeners.pointermove({clientX:450});
  assert.ok(find(chart,"forecastTooltip").textContent.includes("Forecast"));
  assert.ok(find(chart,"forecastTooltip").textContent.includes("Recorded"));
  const dayBar=find(forecast,"forecastDay");
  assert.ok(dayBar?.listeners.pointerenter&&dayBar?.listeners.focus);
  dayBar.listeners.pointerenter();
  assert.ok(find(forecast,"forecastBarTooltip").textContent.includes("Forecast for"));
  assert.equal(find(forecast,"forecastHourly").open,false,
    "hourly forecast list should be collapsed by default");
  assert.equal(find(forecast,"forecastSettingsShell").open,false,
    "configured system settings should be collapsed");
  console.log("Frontend smoke: guide copy, compact costs, forecast pointer/touch/keyboard and bars OK");
}
main().catch(err=>{console.error(err);process.exitCode=1;});
