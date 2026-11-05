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
  window:{customCards:[],confirm:()=>true},
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
const largeHistoryCard=new Card();
largeHistoryCard._historyHours=168;
largeHistoryCard._historyData={solar:Array.from({length:150000},(_,i)=>({
  t:Date.now()-150000+i,y:i%2?12000:-3000
}))};
assert.doesNotThrow(()=>largeHistoryCard._historyChart(),
  "large Recorder responses must not exceed WebView function argument limits");
// HA can configure, connect and publish empty state in either order.
const lifecycle=new Card();
assert.doesNotThrow(()=>{
  lifecycle.setConfig({type:"custom:saj-tou-dynamic-card"});
  lifecycle.connectedCallback();
  lifecycle.hass=undefined;
  lifecycle.hass={states:{"sensor.partial":null,"sensor.restoring":{state:"unavailable"}}};
});
assert.ok(lifecycle.shadowRoot.textContent.includes("No SAJ H2 TOU devices"));
const realRender=lifecycle._renderCard;
const realConsoleError=console.error;
let renderErrors=0;
console.error=()=>renderErrors++;
try{
  lifecycle._drafts.set("editing",{changed:true,start:"17:00"});
  lifecycle._renderCard=()=>{throw Error("temporary rendering failure");};
  assert.doesNotThrow(()=>lifecycle.setConfig({}));
  assert.ok(lifecycle.shadowRoot.textContent.includes("Retry dashboard"));
  assert.equal(lifecycle.shadowRoot.querySelector(".controlPanel"),null);
  lifecycle.hass={states:{}};
  assert.equal(renderErrors,1,"avoid flooding console during repeated failures");
  lifecycle._renderCard=realRender;
  lifecycle.hass={states:{}};
  assert.equal(lifecycle._renderFailed,false,"next state update recovers automatically");
  assert.equal(lifecycle._drafts.get("editing").start,"17:00","preserve unsaved draft");
  lifecycle.connectedCallback();
  assert.equal(lifecycle._renderFailed,false,"resume is read-only and safe");
}finally{console.error=realConsoleError;}
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
  const hoverTarget=Math.round((Date.now()-65000)/30000)*30000;
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
    makeSample(6700,hoverTarget-85000),makeSample(6760)
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
  const asynchronous=probeGrid(
    [makeSample(2000,hoverTarget-20000)],
    [makeSample(6000,hoverTarget)]
  );
  assert.match(asynchronous.text,/Grid ±: -6\.00 kW · exporting/,
    "staggered nonzero sensors must not be subtracted as if simultaneous");
  const stale=probeGrid([], [makeSample(6300,hoverTarget-3*60000)]);
  assert.match(stale.text,/Grid ±: — no nearby reading/,
    "old grid sample outside the nearest-actual tolerance must remain missing");
  const absentGrid=probeGrid([],[]);
  assert.match(absentGrid.text,/Grid ±: — no nearby reading/,
    "only absent import AND export readings should yield a missing-value dash");

  card._historyHours=24;
  card._historyData=null;
  // VPP preview is deliberately read-only. The "Return to
  // Self-consumption" button reuses an existing guarded mode-control path.
  const device={
    id:"saj-test-entry",
    entities:{
      operating_mode:{attributes:{
        raw_mode_code:1,last_verified_read:new Date().toISOString()
      }},
      outside_schedule:{attributes:{raw_fallback_code:1}},
      charge_count:{attributes:{slot_enable_mask:0}},
      discharge_count:{attributes:{slot_enable_mask:0}},
      charge_schedules:{state:"0",attributes:{schedules:[]}},
      discharge_schedules:{state:"0",attributes:{schedules:[]}},
      sync_status:{state:"Verified",attributes:{}}
    }
  };
  const vpp=card._vppQuickActions(device);
  assert.ok(vpp.textContent.includes("VPP quick actions"));
  assert.ok(vpp.textContent.includes("Preview max charge"));
  assert.ok(vpp.textContent.includes("Preview max discharge"));
  assert.ok(vpp.textContent.includes("Return to Self-consumption"));
  assert.ok(vpp.textContent.includes("read-only previews"));
  const buttons=findAll(vpp,"button");
  assert.equal(buttons.length,4,
    "two previews, existing live mode action and separate no-write supervisor status");
  assert.ok(find(vpp,"vppSupervisor"),"watchdog is in a collapsible safety section");
  assert.ok(vpp.textContent.includes("No battery charge/discharge"),
    "dry-run interface must not imply any physical command");
  assert.ok(buttons[0].listeners.click&&buttons[1].listeners.click);
  const ws=[];
  card._hass.callWS=async payload=>{
    ws.push(payload);
    return {response:{
      status:"VPP_PREFLIGHT_ONLY",write_sent:false,
      live_activation_supported:false,can_start:false,
      preflight_passed:false,direction:"charge",
      duration_minutes:10,blockers:["Weekly recurrence requires a watchdog"],
      warnings:[],planned_start_local:"2026-11-02T17:35:00+10:30",
      planned_end_local:"2026-11-02T17:45:00+10:30",
      proposed_slot:1,requested_power_percent_raw:100,
      existing_mode:"Time-of-use",
      battery_soc_percent:92.5,
      battery_soc_source:"fresh inverter 0x406F (double-read)"
    }};
  };
  await buttons[0].listeners.click();
  assert.equal(ws.length,1);
  assert.equal(ws[0].service,"preview_vpp_dispatch");
  assert.equal(ws[0].service_data.direction,"charge");
  assert.equal(ws[0].service_data.duration_minutes,10);
  assert.ok(card._vppPreviewText.includes("No inverter writes sent"));
  assert.ok(card._vppQuickActions(device).textContent.includes(
    "Battery SOC: 92.50% · fresh double-read from inverter"),
    "preflight must show directly verified SOC without cluttering main controls");
  assert.ok(!ws.some(r=>r.service==="apply_schedules"||
    r.service==="supervised_tou_pilot"),
    "preview buttons must never send inverter writes");
  const safeModeButton=buttons[2];
  assert.equal(safeModeButton.disabled,false,
    "self-consumption mode button uses verified state and remains available");
  const reports=[];
  card._hass.callWS=async payload=>{
    reports.push(payload);
    if(payload.service==="vpp_rehearsal_status")
      return {response:{status:"idle",write_sent:false,
        live_activation_supported:false,can_dispatch:false,
        audit:[],baseline_check:"not_checked"}};
    if(payload.service==="start_vpp_safety_rehearsal")
      return {response:{status:"rehearsal_scheduled",write_sent:false,
        live_activation_supported:false,can_dispatch:false,
        audit:[{time_utc:new Date().toISOString(),event:"rehearsal_journaled"}],
        direction:"discharge",ends_utc:new Date().toISOString(),
        baseline_hash:"abc",baseline_check:"verified_at_start"}};
    if(payload.service==="cancel_vpp_safety_rehearsal")
      return {response:{status:"rehearsal_cancelled",write_sent:false,
        live_activation_supported:false,can_dispatch:false,
        audit:[],direction:"discharge",baseline_check:"not_checked"}};
    throw Error("Unexpected service called: "+payload.service);
  };
  await card._callVppSupervisor(device,"vpp_rehearsal_status",{});
  assert.equal(reports[0].service,"vpp_rehearsal_status");
  assert.equal(card._vppSupervisorData.status,"idle");
  card._vppPreviewReport={
    status:"VPP_PREFLIGHT_ONLY",preflight_passed:true,
    direction:"discharge",duration_minutes:5,
    write_sent:false,live_activation_supported:false
  };
  const supervisorPanel=card._vppSupervisorPanel(device);
  const rehearse=findAll(supervisorPanel,"button").find(
    b=>b.textContent==="Run dry-run rehearsal");
  assert.ok(rehearse?.listeners.click,"simulated watchdog starts only after preflight");
  await rehearse.listeners.click();
  assert.equal(reports[1].service,"start_vpp_safety_rehearsal");
  assert.equal(reports[1].service_data.confirmation,
    "SIMULATE ONLY - NO INVERTER WRITES");
  assert.equal(card._vppSupervisorData.status,"rehearsal_scheduled");
  const cancelPanel=card._vppSupervisorPanel(device);
  const cancelButton=findAll(cancelPanel,"button").find(b=>b.textContent==="Cancel rehearsal");
  assert.ok(cancelButton);
  await cancelButton.listeners.click();
  assert.equal(reports[2].service,"cancel_vpp_safety_rehearsal");
  assert.equal(card._vppSupervisorData.status,"rehearsal_cancelled");
  assert.ok(!reports.some(r=>["apply_schedules","supervised_tou_pilot",
    "start_vpp_dispatch","supervised_self_consumption_pilot"].includes(r.service)),
    "safety rehearsals must not invoke any Modbus-writing service");

  // Four-page navigation must physically isolate inverter writes from
  // the read-only Energy page, not merely hide them behind collapsed details.
  // Keep TOU draft changes when navigating to Energy and back.
  const controlRoleStates={
    operating_mode:"Time-of-use",
    outside_schedule:"Self-consumption",
    charge_count:"0",discharge_count:"0",
    charge_schedules:"0",discharge_schedules:"0",
    sync_status:"Verified"
  };
  for(const [role,source] of Object.entries(device.entities)){
    const id="sensor.saj_tou_test_"+role;
    states[id]={entity_id:id,state:controlRoleStates[role],
      attributes:{
        ...source.attributes,saj_tou_role:role,saj_tou_entry_id:device.id
      }};
  }
  card._page="energy";
  card._historyData={solar:[],home:[],battery:[],gridImport:[],gridExport:[]};
  card.render();
  const navigate=label=>{
    const nav=find(card.shadowRoot,"sajNav");
    assert.ok(nav,"navigation must be present");
    const tabs=findAll(nav,"button");
    const target=tabs.find(b=>b.textContent===label);
    assert.ok(target,"expected nav tab "+label);
    target.listeners.click();
    const active=findAll(find(card.shadowRoot,"sajNav"),"button")
      .filter(b=>b.getAttribute("aria-current")==="page");
    assert.equal(active.length,1,"exactly one active page");
    assert.equal(active[0].textContent,label);
  };
  assert.deepEqual(
    findAll(find(card.shadowRoot,"sajNav"),"button").map(b=>b.textContent),
    ["Energy","Control","Costs & savings","Solar forecast"],
    "Energy, Control, Costs and Solar forecast should be separate tabs");
  assert.equal(card._page,"energy","Energy is the safe initial page");
  assert.ok(find(card.shadowRoot,"energyOverview"));
  assert.ok(find(card.shadowRoot,"liveHistory"),
    "Historic Data stays on read-only Energy page");
  assert.ok(find(card.shadowRoot,"costSection"),
    "read-only cost overview stays visible on Energy");
  assert.equal(find(card.shadowRoot,"controlPanel"),undefined);
  assert.equal(find(card.shadowRoot,"vppQuickActions"),undefined);
  assert.ok(!card.shadowRoot.textContent.includes("Save schedule changes to inverter"),
    "Energy must not render any schedule write controls");
  const beforeNavServiceCount=ws.length;
  navigate("Control");
  assert.equal(card._page,"control");
  assert.ok(find(card.shadowRoot,"vppQuickActions"));
  assert.ok(find(card.shadowRoot,"controlPanel"));
  assert.ok(find(card.shadowRoot,"scheduleGrid"));
  assert.equal(find(card.shadowRoot,"energyOverview"),undefined,
    "Live energy/history is not duplicated on Control");
  assert.equal(find(card.shadowRoot,"costSection"),undefined,
    "Cost summary remains read-only on Energy");
  const savedDraft=card._drafts.get(device.id);
  assert.ok(savedDraft,"TOU draft is retained for the selected inverter");
  savedDraft.changed=true;
  navigate("Energy");
  assert.equal(card._drafts.get(device.id),savedDraft,
    "navigating to Energy must not discard unsaved schedule edits");
  assert.equal(card._drafts.get(device.id).changed,true);
  const restoredStates=card._hass.states;
  const unavailableStates=Object.fromEntries(Object.entries(restoredStates).map(([id,state])=>[
    id,{...state,state:"unavailable",attributes:{
      saj_tou_role:state.attributes.saj_tou_role,
      saj_tou_entry_id:state.attributes.saj_tou_entry_id,
      write_controls_available:false
    }}
  ]));
  card.hass={...card._hass,states:unavailableStates};
  assert.equal(card._renderFailed,false,"unavailable readbacks do not break the card");
  assert.equal(card._drafts.get(device.id),savedDraft,"outage preserves unsaved draft");
  card.hass={...card._hass,states:restoredStates};
  card.connectedCallback();
  assert.equal(card._renderFailed,false,"restored readback and app resume recover");
  assert.equal(card._drafts.get(device.id),savedDraft);
  navigate("Control");
  assert.equal(card._drafts.get(device.id).changed,true,
    "navigating back to Control must show the same unsaved draft");
  assert.ok(card.shadowRoot.textContent.includes("Unsaved changes"));
  // Safe Monitor readings change every ~10 seconds; this must NOT force
  // a new rendering of the active Control editor or lose input focus.
  card.hass=card._hass; // establish observed device/energy signatures
  const liveControlTree=card.shadowRoot.children[1];
  states["sensor.saj_h2_safe_monitor_total_solar_power"].state="12345";
  card.hass=card._hass;
  assert.equal(card.shadowRoot.children[1],liveControlTree,
    "new live energy readings cannot redraw focused Control editors");
  assert.equal(card._drafts.get(device.id).changed,true);
  navigate("Costs & savings");
  assert.ok(find(card.shadowRoot,"costEditorShell"));
  assert.equal(find(card.shadowRoot,"vppQuickActions"),undefined);
  assert.equal(find(card.shadowRoot,"controlPanel"),undefined);
  navigate("Solar forecast");
  assert.ok(find(card.shadowRoot,"forecastDay"));
  assert.equal(find(card.shadowRoot,"controlPanel"),undefined);
  navigate("Energy");
  assert.ok(find(card.shadowRoot,"energyOverview"));
  assert.equal(ws.length,beforeNavServiceCount,
    "switching tabs and receiving telemetry must never send a service call");
  // Reset test state for existing detailed costs/forecast checks.
  savedDraft.changed=false;
  states["sensor.saj_h2_safe_monitor_total_solar_power"].state="12410";
  card._page="energy";
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
