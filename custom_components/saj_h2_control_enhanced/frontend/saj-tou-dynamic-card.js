/* SAJ H2 Control Enhanced live TOU controller and read-only energy overview.
 * Reads SAJ Safe Monitor sensors without modifying the safe integration.
 * Live inverter actions require deliberate user interaction and verification.
 */
(() => {
"use strict";
const TAG = "saj-tou-dynamic-card";
if (customElements.get(TAG)) return;
const DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const SAFE_ENERGY_IDS={
  solar:"sensor.saj_h2_safe_monitor_total_solar_power",
  home:"sensor.saj_h2_safe_monitor_home_consumption",
  battery:"sensor.saj_h2_safe_monitor_battery_power",
  soc:"sensor.saj_h2_safe_monitor_battery_state_of_charge",
  stored:"sensor.saj_h2_safe_monitor_estimated_battery_energy",
  gridImport:"sensor.saj_h2_safe_monitor_grid_import_direction_unverified",
  gridExport:"sensor.saj_h2_safe_monitor_grid_export_direction_unverified",
  outlook:"sensor.saj_h2_safe_monitor_today_s_solar_outlook_actual_remaining",
  remaining:"sensor.saj_h2_safe_monitor_solar_forecast_remaining_today",
  tomorrow:"sensor.saj_h2_safe_monitor_tomorrow_s_solar_forecast",
  safeMode:"sensor.saj_h2_safe_monitor_operating_mode"
};
const safeMetric=(hass,key)=>{
  const state=hass?.states?.[SAFE_ENERGY_IDS[key]];
  if(!state || ["unknown","unavailable",""].includes(state.state))return null;
  const numeric=Number(state.state);
  return Number.isFinite(numeric)?numeric:null;
};
const fmtPower=value=>value===null?"—":
  Math.abs(value)>=1000?(Math.abs(value)/1000).toFixed(2)+" kW":
  Math.round(Math.abs(value)).toLocaleString()+" W";
const fmtEnergy=value=>value===null?"—":
  value.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})+" kWh";
const is24Hour = value => /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(value);
function formatLocalTime(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toLocaleString(undefined, {hour12:false,year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"});
}
const CSS = [
  ":host{display:block;color:var(--primary-text-color,#fff)}",
  "ha-card{padding:16px;background:var(--ha-card-background,var(--card-background-color,#202127));border-radius:14px}",
  ".top{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}",
  "h2{font-size:19px;margin:0}h3{font-size:16px;margin:0 0 8px}",
  ".muted{color:var(--secondary-text-color,#aaa);font-size:12px}",
  ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin:14px 0}",
  ".pane{border:1px solid var(--divider-color,#555);border-radius:12px;padding:12px;min-width:0}",
  ".row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:9px 0}",
  ".row label{font-size:12px} .row .spacer{flex:1}",
  ".powerControl{display:flex;flex-direction:column;gap:8px;margin:10px 0 14px}",
  ".powerValues{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}",
  ".powerValues .muted:first-child{margin-right:auto}",
  ".powerControl input[type=range]{width:100%;box-sizing:border-box}",
  ".powerExact{display:flex;align-items:center;gap:8px;font-size:12px}",
  ".powerExact .powerPercentInput{width:82px;min-width:0;box-sizing:border-box}",

  ".pill{font-size:11px;border:1px solid var(--divider-color,#555);border-radius:14px;padding:3px 8px}",
  ".slot{padding:10px 0;border-top:1px solid var(--divider-color,#555)}",
  ".slot header{display:flex;justify-content:space-between;align-items:center;gap:8px}",
  ".days{display:flex;gap:4px;flex-wrap:wrap;margin:8px 0}",
  ".day{border:1px solid var(--divider-color,#555);border-radius:6px;padding:5px;min-width:26px;text-align:center}",
  ".day input{margin:0 3px 0 0}",
  ".inputs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}",
  ".time24{max-width:100%;width:100%;box-sizing:border-box;font-variant-numeric:tabular-nums;font-family:inherit}",
  "input[type=range]{width:100%;min-width:110px;accent-color:var(--primary-color,#16b9b1)}",
  "input,select,button{color:var(--primary-text-color,#fff);background:var(--card-background-color,#24252b);border:1px solid var(--divider-color,#777);border-radius:8px;padding:8px}",
  "button{cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}",
  ".saved{color:var(--secondary-text-color,#aaa);font-size:12px;line-height:1.5;margin:6px 0}",
  ".warn{margin-top:12px;border-left:3px solid var(--warning-color,#d3a435);padding:8px 10px;font-size:12px;background:var(--secondary-background-color,transparent)}",
  ".bad{color:var(--error-color,#ff6c6c)}.okay{color:var(--success-color,#68c99b)}",
  ".empty{padding:16px 4px;color:var(--secondary-text-color,#aaa)}",
  ".toggles{display:flex;align-items:center;gap:8px;flex-wrap:wrap}",
  ".liveModeButtons{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}",
  ".liveModeButtons button{flex:1;min-width:135px}",
  ".liveModeButtons button[aria-pressed=true]{border:2px solid var(--primary-color,#16b9b1)}",
  ".liveResult{font-size:12px;line-height:1.6;overflow-wrap:anywhere;padding:8px;border:1px solid var(--divider-color,#555);border-radius:8px;margin-top:8px}",

  ".energyOverview{border:1px solid var(--divider-color,#555);border-radius:12px;padding:12px;margin:16px 0;background:var(--secondary-background-color,transparent)}",
  ".energyOverview .flowTop{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}",
  ".energyOverview h3{font-size:17px;margin:0}",
  ".flowScroll{overflow-x:auto;margin-top:12px}",
  ".flowTable{width:100%;border-collapse:collapse;table-layout:fixed;min-width:610px}",
  ".flowTable th,.flowTable td{border:1px solid var(--divider-color,#444);padding:7px 6px;text-align:center;font-size:12px;vertical-align:middle}",
  ".flowTable th{font-weight:700;white-space:nowrap}",
  ".flowTable .flowNumbers td{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}",
  ".flowSummary{font-weight:600;margin-top:12px;font-size:13px}",
  ".flowGraph{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0 4px}",
  ".flowGraphCell{min-width:0}",
  ".flowGraphCaption{display:flex;justify-content:space-between;align-items:center;font-size:12px;gap:4px}",
  ".flowGraphCaption b{font-variant-numeric:tabular-nums}",
  ".flowGraphTrack{height:8px;border-radius:999px;background:var(--divider-color,#444);overflow:hidden;margin-top:6px}",
  ".flowGraphFill{height:100%;background:var(--primary-color,#16b9b1);border-radius:999px}",
  ".socFlow{margin-top:12px}",
  ".socFlowTop{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px}",
  ".flowFoot{font-size:11px;color:var(--secondary-text-color,#aaa);line-height:1.5;margin-top:12px}",

  "ha-card{padding:18px 20px 22px;border-radius:16px;--control-accent:var(--primary-color,#16b9b1);background:var(--ha-card-background,var(--card-background-color,#1c1f23))}",
  ".deviceChooser{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 14px;margin:0 0 14px;border:1px solid var(--divider-color,#45484c);border-radius:12px;background:var(--card-background-color,#222528);flex-wrap:wrap}",
  ".deviceChooserHeading{display:flex;flex-direction:column;gap:4px}.deviceChooserHeading strong{font-size:14px}.deviceChooser select{min-width:230px;max-width:100%;flex:0 1 380px;font-weight:600}",

  ".readbackBar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:0 0 12px;font-size:12px}",
  ".readbackOk{color:var(--success-color,#77cf99);font-weight:650}.readbackBad{color:var(--error-color,#f66);font-weight:650}",
  ".energyOverview{margin:12px 0 16px;padding:18px;border-radius:14px;background:linear-gradient(140deg,rgba(31,167,175,.045),transparent 48%),var(--card-background-color,#22272a)}",
  ".energyHeading{display:flex;flex-direction:column;gap:4px}.energyHeading .muted{font-size:11px}",
  ".energyOverview h3{font-size:17px;letter-spacing:.1px}",
  ".flowScroll{margin-top:16px;border:1px solid var(--divider-color,#45484c);border-radius:11px}",
  ".flowTable{border-collapse:separate;border-spacing:0;min-width:640px}",
  ".flowTable th{border:none;border-right:1px solid var(--divider-color,#45484c);border-bottom:1px solid var(--divider-color,#45484c);padding:11px 7px;font-size:12px;background:rgba(128,128,128,.055)}",
  ".flowTable th:last-child,.flowTable td:last-child{border-right:0}",
  ".flowTable tr:last-child td{border-bottom:0}",
  ".flowTable td{border:0;border-right:1px solid var(--divider-color,#45484c);border-bottom:1px solid var(--divider-color,#45484c);padding:10px 7px;font-size:12px}",
  ".flowTable .flowNumbers td{font-size:17px;font-weight:750;letter-spacing:.1px}",
  ".flowGraph{gap:14px;margin:18px 0 8px}.flowGraphTrack{height:9px}",
  ".socFlow{margin-top:14px;padding-top:12px;border-top:1px solid var(--divider-color,#45484c)}",
  ".flowSummary{margin-top:14px;font-size:12px}",
  ".controlPanel{border:1px solid var(--divider-color,#45484c);border-radius:14px;margin:0 0 18px;background:var(--card-background-color,#222528);overflow:hidden}",
  ".controlPanelHead{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:13px 18px;border-bottom:1px solid var(--divider-color,#45484c);background:rgba(128,128,128,.045)}",
  ".controlPanelHead h3{margin:0;font-size:16px}",
  ".controlColumns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}",
  ".controlCell{padding:16px 18px 17px;min-width:0}",
  ".controlCell+.controlCell{border-left:1px solid var(--divider-color,#45484c)}",
  ".controlCell h4{font-size:14px;font-weight:650;margin:0 0 5px}",
  ".controlCell .saved{margin:0 0 12px}",
  ".controlCell p.muted{font-size:12px;line-height:1.6;margin:11px 0 0;max-width:55ch}",
  ".controlCell select{min-width:220px;max-width:100%;padding:10px 12px}",
  ".controlCell .liveModeButtons{margin:8px 0 12px;flex-wrap:nowrap}",
  ".controlCell .liveModeButtons button{min-width:0;flex:1;padding:12px 10px;font-size:12px}",
  ".controlCell .liveModeButtons button[aria-pressed=true]{background:rgba(23,167,173,.12);border:1px solid var(--control-accent);opacity:1!important;color:var(--primary-text-color,#fff);font-weight:700}",
  ".controlCell .liveModeButtons button[aria-pressed=true]:disabled{cursor:default}",
  ".controlCell button:hover:not(:disabled),.scheduleActions button:hover:not(:disabled){border-color:var(--control-accent)}",
  ".controlCell .liveResult{margin-top:12px}",
  ".scheduleTitle{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin:12px 0 4px}",
  ".scheduleTitle h3{font-size:16px;margin:0}",
  ".scheduleGrid{margin-top:10px;gap:12px}",
  ".scheduleGrid .pane{padding:16px;border-radius:14px;background:var(--card-background-color,#222528)}",
  ".scheduleGrid .pane h3{font-size:15px}",
  ".scheduleActions{margin:14px 0 8px;gap:10px}",
  ".scheduleActions button{font-weight:600;padding:11px 14px}",
  ".primaryAction:not(:disabled){background:var(--control-accent);border-color:var(--control-accent);color:var(--text-primary-color,#07161a)}",
  ".warn{font-size:12px;line-height:1.55;border-radius:0 9px 9px 0}",
  "@media(max-width:780px){.controlColumns{grid-template-columns:1fr}.controlCell+.controlCell{border-left:0;border-top:1px solid var(--divider-color,#45484c)}.controlCell{padding:15px}.controlPanelHead{padding:12px 15px}.energyOverview{padding:13px}.flowTable .flowNumbers td{font-size:15px}}",

  "@media(max-width:650px){.flowGraph{grid-template-columns:repeat(2,minmax(0,1fr))}.flowTable th,.flowTable td{font-size:11px;padding:6px 4px}}",

].join("");
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = String(text);
  return node;
};
const add = (parent, ...children) => {children.forEach(c => parent.append(c)); return parent;};
const isValid = state => state && !["unknown","unavailable"].includes(state.state);
const roles = ["operating_mode","outside_schedule","charge_count","discharge_count","charge_schedules","discharge_schedules","sync_status"];
const suffixes = {
  operating_mode:"_operating_mode",
  outside_schedule:"_outside_schedule_behaviour",
  charge_count:"_enabled_charge_schedules",
  discharge_count:"_enabled_discharge_schedules",
  charge_schedules:"_charge_schedules",
  discharge_schedules:"_discharge_schedules",
  sync_status:"_tou_device_sync"
};
function findDevices(hass) {
  const groups = new Map();
  Object.entries(hass.states || {}).forEach(([id, state]) => {
    if (!id.startsWith("sensor.")) return;
    let role = state.attributes.saj_tou_role;
    if (!roles.includes(role)) {
      // Compatibility with older v0.1.x entity IDs.
      role = roles.find(r => id.endsWith(suffixes[r]));
      if (!role || !id.includes("tou_readback")) return;
    }
    const group = state.attributes.saj_tou_entry_id ||
      id.slice(0, id.length - (suffixes[role] || "").length);
    if (!groups.has(group)) groups.set(group, {id:group, entities:{}});
    groups.get(group).entities[role] = state;
  });
  return [...groups.values()].filter(g => g.entities.discharge_schedules || g.entities.charge_schedules);
}
function cleanTime(t) {return /^\d\d:\d\d$/.test(t) ? t : "00:00";}
function cloneDraft(group) {
  const e = group.entities;
  function rows(role) {
    const state = e[role];
    const active = (state && state.attributes.schedules) || [];
    return active.slice(0,7).map(v=>({
      slotNumber:Number(v.slot),
      savedStart:cleanTime(v.start), savedEnd:cleanTime(v.end),
      savedDayMask:Number(v.weekday_mask_raw)||0,
      savedPercent:Number(v.power_percent_raw)||0,
      start:cleanTime(v.start),end:cleanTime(v.end),
      percent:Math.max(0,Math.min(100,Number(v.power_percent_raw)||0)),
      dayMask:Number(v.weekday_mask_raw)||0,
      // Read all seven bits; Sat(32)/Sun(64) individual meanings are
      // inferred from the observed paired weekend mask 96.
      days: DAYS.filter((day,i)=>
        Boolean((Number(v.weekday_mask_raw)||0) & (1<<i))),
      original:true
    }));
  }
  return {
    mode: e.operating_mode && e.operating_mode.state==="Time-of-use" ? "Time-of-use" : "Self-consumption",
    fallback: e.outside_schedule && e.outside_schedule.state==="Standby" ? "Standby" : "Self-consumption",
    charge:rows("charge_schedules"),discharge:rows("discharge_schedules"),
    baselineCharge:(e.charge_schedules?.attributes.schedules||[]).map(v=>({
      slot:Number(v.slot),start:v.start,end:v.end,
      day_mask:Number(v.weekday_mask_raw),percent:Number(v.power_percent_raw)
    })),
    baselineDischarge:(e.discharge_schedules?.attributes.schedules||[]).map(v=>({
      slot:Number(v.slot),start:v.start,end:v.end,
      day_mask:Number(v.weekday_mask_raw),percent:Number(v.power_percent_raw)
    })),
    changed:false
  };
}
class SajTOUDynamicCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._cfg = {};
    this._drafts = new Map();
    this._selected = "";
    this._lastSignature = "";
    this._lastEnergySignature = "";
    this._modeBusy = false;
    this._fallbackBusy = false;
    this._fallbackFeedback = "";
    this._fallbackFeedbackError = false;
    this._modeFeedback = "";
    this._modeFeedbackError = false;
    this._modeBusyEntry = "";
    this._refreshBusy = false;
    this._schedulePreview = new Map();
    this._previewBusy = false;
    this._scheduleWriteBusy = false;
    this._scheduleWriteFeedback = "";
    this._scheduleWriteError = false;
    this._schedulePlan = null;
    this._schedulePlanKey = "";
  }
  setConfig(config) {this._cfg=config||{};this.render();}
  set hass(hass) {
    this._hass=hass;
    // Only re-render if actual published state/attributes changed,
    // preserving controls and their current focus between HA updates.
    const devices = findDevices(hass);
    const sig = devices.map(g => [g.id, ...roles.map(r => {
      const s=g.entities[r]; return s ? s.state+"|"+JSON.stringify(s.attributes.schedules || [])+"|"+(s.attributes.last_verified_read||""):"";
    })].join(":")).join(";");
    const energySig=Object.values(SAFE_ENERGY_IDS).map(id=>
      hass.states?.[id]?.state??"—").join("|");
    if (sig!==this._lastSignature) {
      this._lastSignature=sig;
      this._lastEnergySignature=energySig;
      // Follow external elekeeper changes unless the user is editing a draft.
      devices.forEach(g=>{
        const existing=this._drafts.get(g.id);
        if (existing && !existing.changed) this._drafts.set(g.id,cloneDraft(g));
      });
      this.render();
    } else if(energySig!==this._lastEnergySignature) {
      this._lastEnergySignature=energySig;
      // Updating safe monitoring graphics must not reset an active time input
      // or discard an in-progress TOU schedule draft.
      const old=this.shadowRoot?.querySelector(".energyOverview");
      if(old)old.replaceWith(this._energyOverview());
      else this.render();
    }
  }
  getCardSize() {return 7;}
  getStubConfig() {return {};}
  _energyOverview(){
    const hass=this._hass;
    const panel=el("section","energyOverview");
    const header=el("div","flowTop");
    const energyHeading=el("div","energyHeading");
    add(energyHeading,el("h3",null,"Live energy"),
      el("div","muted","Solar · Home · Battery · Grid · Forecast"));
    add(header,energyHeading,el("span","pill","● Read-only telemetry"));
    add(panel,header);
    const keys=["solar","home","battery","soc","stored","gridImport",
      "gridExport","outlook","remaining","tomorrow"];
    const values=Object.fromEntries(keys.map(k=>[k,safeMetric(hass,k)]));
    if(keys.every(k=>values[k]===null)){
      add(panel,el("p","muted",
        "Live energy readings unavailable. This visual panel uses existing "+
        "SAJ H2 Safe Monitor sensors and never changes inverter settings."));
      return panel;
    }
    const solar=values.solar,home=values.home,battery=values.battery;
    const imp=values.gridImport,exp=values.gridExport;
    const batteryStatus=battery===null?"Unavailable":
      battery>15?"Discharging ↗":battery< -15?"Charging ↙":"Idle";
    const gridStatus=imp!==null&&imp>15?"Import":
      exp!==null&&exp>15?"Export":
      imp!==null&&exp!==null?"No net exchange":"Direction not available";
    const tableWrap=el("div","flowScroll");
    const table=el("table","flowTable");
    const head=el("thead");
    const hr=el("tr");
    for(const title of ["☀️ Solar","🏠 House","🔋 Battery","⚡ Grid","🔮 Forecast"])
      add(hr,el("th",null,title));
    add(head,hr);add(table,head);
    const body=el("tbody");
    const r1=el("tr","flowNumbers");
    for(const cell of [
      fmtPower(solar),fmtPower(home),fmtPower(battery),
      fmtPower(imp),
      values.outlook===null?"—":fmtEnergy(values.outlook)+" Today"
    ]) add(r1,el("td",null,cell));
    const r2=el("tr");
    for(const cell of [
      solar===null?"—":"Generating",
      home===null?"—":"Using",
      batteryStatus,
      imp===null?"—":"Import",
      values.remaining===null?"—":fmtEnergy(values.remaining)+" remaining"
    ]) add(r2,el("td",null,cell));
    const r3=el("tr");
    const socLabel=values.soc===null?"—":values.soc.toFixed(1)+"% SOC";
    for(const cell of [
      "","",
      socLabel+" · "+fmtEnergy(values.stored)+" stored",
      exp===null?"—":fmtPower(exp)+" export",
      values.tomorrow===null?"—":fmtEnergy(values.tomorrow)+" tomorrow"
    ])add(r3,el("td",null,cell));
    add(body,r1,r2,r3);add(table,body);add(tableWrap,table);
    add(panel,tableWrap);
    // Relative bar lengths use only current wattage values, not invented
    // energy-routing predictions or guessed historical samples.
    const powerItems=[
      ["Solar",solar],["House",home],["Battery",battery===null?null:Math.abs(battery)],
      ["Grid",imp===null&&exp===null?null:Math.max(imp||0,exp||0)]
    ];
    const maximum=Math.max(1,...powerItems.map(([,v])=>v===null?0:Math.abs(v)));
    const graph=el("div","flowGraph");
    for(const [label,value] of powerItems){
      const cell=el("div","flowGraphCell");
      const caption=el("div","flowGraphCaption");
      add(caption,el("span",null,label),el("b",null,fmtPower(value)));
      const track=el("div","flowGraphTrack");
      const fill=el("div","flowGraphFill");
      fill.style.width=value===null?"0%":
        Math.min(100,Math.max(0,Math.abs(value)/maximum*100))+"%";
      track.append(fill);add(cell,caption,track);graph.append(cell);
    }
    add(panel,graph);
    if(values.soc!==null){
      const socBox=el("div","socFlow");
      const top=el("div","socFlowTop");
      add(top,el("span",null,"Battery state of charge"),
        el("strong",null,values.soc.toFixed(1)+"% · "+
          fmtEnergy(values.stored)+" stored"));
      const track=el("div","flowGraphTrack");
      const fill=el("div","flowGraphFill");
      fill.style.width=Math.max(0,Math.min(100,values.soc))+"%";
      track.append(fill);add(socBox,top,track);add(panel,socBox);
    }
    const modeState=hass.states?.[SAFE_ENERGY_IDS.safeMode]?.state;
    add(panel,el("div","flowSummary",gridStatus+
      ((modeState&&!["unavailable","unknown"].includes(modeState))?
        " · "+modeState:"")));
    add(panel,el("div","flowFoot",
      "Forecast combines measured and predicted energy and is an estimate. "+
      "Grid import/export direction remains provisional. Monitoring and "+
      "graphics are read-only; TOU control actions are separate."));
    return panel;
  }
  render() {
    if (!this.shadowRoot || !this._hass) return;
    const devices = findDevices(this._hass);
    if (!devices.some(g=>g.id===this._selected)) this._selected=devices[0]&&devices[0].id || "";
    const group = devices.find(g=>g.id===this._selected);
    const root =this.shadowRoot;
    root.replaceChildren();
    add(root, el("style",null,CSS));
    const card=el("ha-card");
    root.append(card);
    // Home Assistant provides the "SAJ H2 Control" native view title.
    // Avoid repeating that heading, a second large title, or an unnecessary
    // device dropdown when there is only one configured inverter.
    if (!group) {
      add(card,el("p","empty","No SAJ H2 TOU devices found. Check the SAJ TOU control integration and its schedule sensors."));
      return;
    }
    if(devices.length>1){
      // A custom Lovelace card cannot safely add a control inside Home
      // Assistant's own native toolbar. Put the multi-device selector
      // directly below that toolbar, ahead of telemetry or live controls.
      const chooser=el("div","deviceChooser");
      const heading=el("div","deviceChooserHeading");
      add(heading,el("strong",null,"Select SAJ inverter"),
        el("span","muted",devices.length+" devices available"));
      const select=el("select");
      select.setAttribute("aria-label","Active SAJ inverter");
      const names=devices.map(g=>
        (g.entities.operating_mode?.attributes.friendly_name||"SAJ H2")
          .replace(/ Operating mode$/i,"").trim()||"SAJ H2");
      devices.forEach((g,index)=>{
        const duplicated=names.filter(name=>name===names[index]).length>1;
        const name=duplicated?names[index]+" · Device "+(index+1):names[index];
        const opt=el("option",null,name);
        opt.value=g.id;opt.selected=g.id===group.id;select.append(opt);
      });
      select.addEventListener("change",e=>{
        this._selected=e.target.value;
        this._schedulePlan=null;this._schedulePlanKey="";
        this._modeFeedback="";this._fallbackFeedback="";
        this._scheduleWriteFeedback="";
        this.render();
      });
      add(chooser,heading,select);add(card,chooser);
    }
    const e=group.entities;
    const good=roles.every(r => isValid(e[r]));
    const status=el("div","readbackBar");
    const statusIndicator=el("span",good?"readbackOk":"readbackBad",
      good?"● Connected to inverter":"● Readback unavailable");
    add(status,statusIndicator,
      el("span","muted","Last verified: "+formatLocalTime(e.sync_status?.attributes.last_verified_read)));
    add(card,status);
    add(card,this._energyOverview());
    if (!this._drafts.has(group.id)) this._drafts.set(group.id,cloneDraft(group));
    const draft=this._drafts.get(group.id);
    const meta=el("section","controlPanel");
    const metaHead=el("div","controlPanelHead");
    add(metaHead,el("h3",null,"Inverter controls"),
      el("span","pill","Mode · Outside TOU"));
    add(meta,metaHead);
    const controlColumns=el("div","controlColumns");
    const modepane=el("div","controlCell");
    add(modepane,el("h4",null,"Operating mode"),
      el("div","saved","Device: "+(e.operating_mode?.state||"unknown")));
    const modeValue=e.operating_mode?.attributes.raw_mode_code;
    const freshTime=e.operating_mode?.attributes.last_verified_read;
    const ageSeconds=freshTime?(Date.now()-new Date(freshTime).getTime())/1000:Infinity;
    const canOperate=good && Number.isInteger(modeValue) &&
      (modeValue===0 || modeValue===1) &&
      [0,1].includes(e.outside_schedule?.attributes.raw_fallback_code) &&
      Number.isFinite(ageSeconds) && ageSeconds>=0 && ageSeconds<=180 &&
      !this._modeBusy && !this._fallbackBusy && !draft.changed &&
      Number.isInteger(e.charge_count?.attributes.slot_enable_mask) &&
      e.charge_count?.attributes.slot_enable_mask>=0 &&
      e.charge_count?.attributes.slot_enable_mask<=127 &&
      Number.isInteger(e.discharge_count?.attributes.slot_enable_mask) &&
      e.discharge_count?.attributes.slot_enable_mask>=0 &&
      e.discharge_count?.attributes.slot_enable_mask<=127;
    const controls=el("div","liveModeButtons");
    for (const [target,text,service] of [
      [0,"Self-consumption","supervised_self_consumption_pilot"],
      [1,"Time-of-Use","supervised_tou_pilot"],
    ]) {
      const button=el("button",null,text);
      button.type="button";
      button.disabled=!canOperate || modeValue===target;
      button.setAttribute("aria-pressed",String(modeValue===target));
      button.title=modeValue===target?"Already current mode":
        "One confirmed live inverter operating-mode write";
      button.addEventListener("click",()=>this._requestMode(group,target,service));
      controls.append(button);
    }
    const blockers=[];
    if (!good) blockers.push("one or more sensor readings unavailable");
    if (!Number.isInteger(modeValue) || ![0,1].includes(modeValue)) blockers.push("unsupported mode reading");
    if (![0,1].includes(e.outside_schedule?.attributes.raw_fallback_code)) blockers.push("unsupported outside-TOU setting");
    if (!Number.isFinite(ageSeconds) || ageSeconds<0 || ageSeconds>180) blockers.push("readback older than 3 minutes");
    if (draft.changed) blockers.push("local draft modified");
    if (!Number.isInteger(e.charge_count?.attributes.slot_enable_mask) ||
        !Number.isInteger(e.discharge_count?.attributes.slot_enable_mask))
      blockers.push("schedule enable masks unavailable");
    const refresh=el("button",null,this._refreshBusy?"Refreshing…":"Refresh inverter state");
    refresh.type="button";refresh.disabled=this._refreshBusy||this._modeBusy||this._fallbackBusy;
    refresh.addEventListener("click",()=>this._refreshMode(group));
    add(modepane,controls,refresh,
      el("p","muted",
        this._modeBusy?"Applying and verifying mode; do not click again.":
        blockers.length?"Live switch blocked: "+blockers.join("; ")+". Refresh to recheck.":
        "Live mode control uses a confirmed one-shot Modbus action. elekeeper overview can lag."));
    if (this._modeFeedback) {
      add(modepane,el("div","liveResult "+(this._modeFeedbackError?"bad":"okay"),this._modeFeedback));
    }
    const fallbackPane=el("div","controlCell");
    add(fallbackPane,el("h4",null,"Outside TOU windows"),
      el("div","saved","Device: "+(e.outside_schedule?.state||"unknown")));
    const fallbackRaw=e.outside_schedule?.attributes.raw_fallback_code;
    const fallbackSelect=el("select");
    for(const [raw,label] of [[1,"Self-consumption"],[0,"Standby"]]){
      const option=el("option",null,label);
      option.value=String(raw);
      option.selected=raw===fallbackRaw;
      fallbackSelect.append(option);
    }
    fallbackSelect.setAttribute("aria-label","Outside TOU windows setting");
    const fallbackReadAt=e.outside_schedule?.attributes.last_verified_read;
    const fallbackAge=fallbackReadAt?
      (Date.now()-new Date(fallbackReadAt).getTime())/1000:Infinity;
    fallbackSelect.disabled=![0,1].includes(fallbackRaw) || ![0,1].includes(modeValue) ||
      !good || this._fallbackBusy || this._modeBusy || this._scheduleWriteBusy ||
      !Number.isFinite(fallbackAge) || fallbackAge<0 || fallbackAge>180;
    fallbackSelect.addEventListener("change",()=>{
      const target=Number(fallbackSelect.value);
      // Device is the source of truth; show the new state only on verified readback.
      fallbackSelect.value=String(fallbackRaw);
      this._changeOutsideTOU(group,target);
    });
    add(fallbackPane,fallbackSelect,
      el("p","muted",
        this._fallbackBusy?"Applying and verifying inverter setting…":
        "Self-consumption uses the battery outside scheduled periods. "+
        "Standby may stop battery charging/discharging outside TOU periods."));
    if(this._fallbackFeedback){
      add(fallbackPane,el("div","liveResult "+(this._fallbackFeedbackError?"bad":"okay"),
        this._fallbackFeedback));
    }
    add(controlColumns,modepane,fallbackPane);
    add(meta,controlColumns);add(card,meta);
    const sectionHead=el("div","scheduleTitle");
    add(sectionHead,el("h3",null,"Charging & discharging schedules"),
      el("span","muted","Up to 7 periods each"));
    add(card,sectionHead);
    const columns=el("div","grid scheduleGrid");
    add(columns,this.scheduleSection(group,"charge",draft),this.scheduleSection(group,"discharge",draft));
    add(card,columns);
    if (draft.changed) add(card,el("div","warn","Unsaved changes — use Save schedule changes to inverter. Reload discards these edits; the saved device schedule remains unchanged until a confirmed save succeeds."));
    const footer=el("div","row scheduleActions");
    const reset=el("button","secondaryAction","Discard edits / reload inverter");
    reset.addEventListener("click",()=>{
      if(draft.changed && !window.confirm("Discard unsaved schedule changes and reload inverter settings?"))return;
      this._drafts.set(group.id,cloneDraft(group));
      this._schedulePlan=null;this._schedulePlanKey="";this._schedulePreview.clear();
      this.render();
    });
    const save=el("button","primaryAction",
      this._scheduleWriteBusy?"Applying & verifying…":
      this._previewBusy?"Validating saved settings…":
      "Save schedule changes to inverter");
    const canSave=draft.changed &&
      [0,1].includes(e.operating_mode?.attributes.raw_mode_code) &&
      !this._scheduleWriteBusy && !this._previewBusy && !this._modeBusy && !this._fallbackBusy;
    save.disabled=!canSave;
    save.title=canSave?
      "Validate live device settings, confirm, and save changed schedule registers":
      "Make a schedule edit to enable saving";
    save.addEventListener("click",()=>this._saveSchedules(group));
    add(footer,reset,save);add(card,footer);
    if(draft.changed && ![0,1].includes(e.operating_mode?.attributes.raw_mode_code))
      add(card,el("div","warn",
        "Unsupported operating mode: saving schedule edits is blocked."));
    if(this._scheduleWriteFeedback)
      add(card,el("div","liveResult "+(this._scheduleWriteError?"bad":"okay"),
        this._scheduleWriteFeedback));
    const change=e.sync_status?.attributes.last_changes;
    if (Array.isArray(change)&&change.length) {
      add(card,el("p","muted","Last detected change: "+change.join("; ")));
    }
    add(card,el("div","warn","Edit times, weekdays (Mon–Sun) and power, then Save; the app validates first and asks once. For an overnight interval, use Split overnight into two slots. Weekend individual bit positions are inferred from paired Sat+Sun readback. Multiple writes are not atomic: after any error check elekeeper before retrying. Power labels are estimates based on stored raw values."));
  }
  async _changeOutsideTOU(group,target){
    if(this._fallbackBusy || this._modeBusy || this._scheduleWriteBusy)return;
    const device=this._hass?findDevices(this._hass).find(g=>g.id===group.id):null;
    const e=device?.entities;
    const before=e?.outside_schedule?.attributes.raw_fallback_code;
    const operating=e?.operating_mode?.attributes.raw_mode_code;
    const readAt=e?.outside_schedule?.attributes.last_verified_read;
    const age=readAt?(Date.now()-new Date(readAt).getTime())/1000:Infinity;
    if(![0,1].includes(before)||![0,1].includes(operating)||
       ![0,1].includes(target)||before===target||!Number.isFinite(age)||
       age<0||age>180){
      this._fallbackFeedback="Setting changed or reading is stale. Refresh inverter state first.";
      this._fallbackFeedbackError=true;this.render();return;
    }
    if(target===0 && !window.confirm(
      "Enable Standby outside Time-of-Use periods?\n\n"+
      "The battery may stop charging or discharging when no TOU schedule is active. "+
      "This can change grid imports and how solar energy is used.\n\n"+
      "Your charging/discharging schedules and operating mode will be preserved. "+
      "Continue?"))return;
    this._fallbackBusy=true;
    this._fallbackFeedback="Sending outside-TOU setting and verifying Modbus readback…";
    this._fallbackFeedbackError=false;this.render();
    try{
      const data={
        target_fallback:target,expected_fallback:before,expected_mode:operating,
        device_model:"H2-10K-S3-A",control_firmware:"v2.018"
      };
      if(target===0)data.standby_confirmation="I CONFIRM STANDBY OUTSIDE TOU";
      if(group.id&&!group.id.startsWith("sensor."))data.entry_id=group.id;
      const result=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"supervised_outside_tou_fallback",service_data:data,
        return_response:true
      });
      const report=result?.response||result;
      if(report?.status!=="FALLBACK_VERIFIED_BY_MODBUS"||
         report?.after_fallback_raw!==target||report?.write_sent!==true||
         report?.mode_unchanged!==true||
         report?.charge_and_discharge_unchanged!==true)
        throw new Error("No fully verified device response");
      this._fallbackFeedback="Verified by Modbus: outside TOU periods now use "+
        (target===0?"Standby":"Self-consumption")+
        ". Operating mode and schedules remain unchanged. elekeeper may lag.";
      this._fallbackFeedbackError=false;
    }catch(err){
      this._fallbackFeedback="Unable to verify the change: "+
        (err?.message||String(err))+
        ". Command may already have been sent. Inspect elekeeper before retrying.";
      this._fallbackFeedbackError=true;
    }finally{
      this._fallbackBusy=false;this.render();
    }
  }
  async _refreshMode(group) {
    if(this._refreshBusy||this._modeBusy||this._fallbackBusy)return;
    this._refreshBusy=true;this._modeFeedback="Refreshing live Modbus readback…";
    this._modeFeedbackError=false;this.render();
    try{
      const data={target_mode:"time_of_use"};
      if(group.id && !group.id.startsWith("sensor."))data.entry_id=group.id;
      const result=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"preview_mode_change",service_data:data,return_response:true
      });
      const report=result?.response||result;
      if(report?.status!=="DRY_RUN_ONLY"||report.write_sent!==false)
        throw new Error("No safe Modbus confirmation returned");
      this._modeFeedback="Fresh device read succeeded; no settings changed. Mode "+
        (report.inverter_mode_raw===1?"Time-of-Use":"Self-consumption")+
        ", schedule masks ["+report.charge_enable_mask+", "+report.discharge_enable_mask+"].";
      this._modeFeedbackError=false;
    }catch(err){
      this._modeFeedbackError=true;
      this._modeFeedback="Refresh failed: "+(err?.message||String(err));
    }finally{this._refreshBusy=false;this.render();}
  }
  async _requestMode(group,target,service) {
    if (this._modeBusy||this._fallbackBusy) return;
    const current=group.entities.operating_mode?.attributes.raw_mode_code;
    const fallback=group.entities.outside_schedule?.attributes.raw_fallback_code;
    const charge=group.entities.charge_count?.attributes.slot_enable_mask;
    const discharge=group.entities.discharge_count?.attributes.slot_enable_mask;
    const source=group.entities.operating_mode?.attributes.last_verified_read;
    const age=source ? (Date.now()-new Date(source).getTime())/1000 : Infinity;
    const draft=this._drafts.get(group.id);
    if (!Number.isInteger(current) || current!==1-target || ![0,1].includes(fallback) ||
        !Number.isInteger(charge) || charge<0 || charge>127 ||
        !Number.isInteger(discharge) || discharge<0 || discharge>127 ||
        !Number.isFinite(age) || age<0 ||
        age>180 || (draft&&draft.changed)) {
      this._modeFeedback="Blocked: device state changed or became stale. Reload and verify.";
      this._modeFeedbackError=true;
      this.render();return;
    }
    const label=target===1?"Time-of-Use":"Self-consumption";
    const phrase=target===1?"I AUTHORIZE ONE TOU MODE WRITE":
      "I AUTHORIZE ONE SELF CONSUMPTION MODE WRITE";
    if (!window.confirm("LIVE INVERTER CONTROL: switch from "+
      (current===0?"Self-consumption":"Time-of-Use")+" to "+label+
      "?\n\nThis may change battery charging/discharging and grid exports."+
      (target===1 && fallback===0 ?
        "\nWARNING: Outside TOU windows is set to Standby. "+
        "The battery may enter Standby outside your scheduled periods." : "")+
      "\nSaved schedules will not be edited. Have elekeeper available.")) return;
    this._modeBusy=true;
    this._modeBusyEntry=group.id;
    this._modeFeedback="Sending one confirmed command and checking inverter readback…";
    this._modeFeedbackError=false;
    this.render();
    try {
      // HA WebSocket call_service supports return_response for services with
      // SupportsResponse.ONLY. No direct Modbus access from the card.
      const data={
        confirmation:phrase,device_model:"H2-10K-S3-A",control_firmware:"v2.018"
      };
      if (target===1) data.expected_current_mode=0;
      if (group.id && !group.id.startsWith("sensor.")) data.entry_id=group.id;
      const payload={
        type:"call_service",domain:"saj_h2_control_enhanced",
        service,service_data:data,return_response:true
      };
      const answer=await this._hass.callWS(payload);
      const report=answer?.response||answer;
      if (report?.status!=="VERIFIED_BY_MODBUS" ||
          report?.after_mode_raw!==target || report?.write_sent!==true) {
        throw new Error("No verified device response. Do NOT retry automatically. Check elekeeper and Modbus.");
      }
      this._modeFeedback="Verified by Modbus: inverter now reports "+label+
        ". Schedules and fallback unchanged. elekeeper display may lag.";
      this._modeFeedbackError=false;
    } catch(error) {
      this._modeFeedbackError=true;
      this._modeFeedback="Unable to confirm mode change: "+
        (error?.message||String(error))+
        ". A write may already have been sent. Do NOT repeat the action. Check elekeeper.";
    } finally {
      this._modeBusy=false;this._modeBusyEntry="";
      this.render();
    }
  }
  async _validateSchedule(group,direction,row,saved) {
    if(this._previewBusy)return;
    if (!is24Hour(row.start) || !is24Hour(row.end)) {
      this._schedulePreview.set(group.id+":"+direction+":"+row.slotNumber,{
        error:true,message:"Invalid time: use the native 24-hour selector (00:00–23:59). NO WRITE"
      });
      this.render();return;
    }
    // Do not accept a derived/unknown weekday mapping as a writable plan.
    // The backend independently checks raw mask and latest full readback.
    const data={
      direction,slot:Number(row.slotNumber),
      expected_start:row.savedStart,expected_end:row.savedEnd,
      expected_day_mask:row.savedDayMask,
      expected_power_percent:row.savedPercent,
      start:row.start,end:row.end,
      weekdays:[...row.days],power_percent:Number(row.percent)
    };
    if(group.id && !group.id.startsWith("sensor."))data.entry_id=group.id;
    const key=group.id+":"+direction+":"+row.slotNumber;
    this._previewBusy=true;this.render();
    try {
      const result=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"preview_schedule_change",service_data:data,return_response:true
      });
      const report=result?.response||result;
      if(report?.status!=="SCHEDULE_DRY_RUN_ONLY"||report?.write_sent!==false)
        throw new Error("Invalid dry-run response; no changes authorised");
      this._schedulePreview.set(key,{error:false,message:
        "Valid draft · "+(report.change_needed?"Change proposed":"Already matches")+
        " · Registers "+report.register_addresses.map(x=>"0x"+x.toString(16)).join(", ")+
        " · Existing ["+report.existing_words.join(", ")+"] → proposed ["+
        report.proposed_words.join(", ")+"] · NO WRITE"});
    }catch(err){
      this._schedulePreview.set(key,{error:true,message:
        "Draft validation blocked: "+(err?.message||String(err))+" · NO WRITE"});
    }finally{this._previewBusy=false;this.render();}
  }
  _fullDraftPayload(group) {
    const d=this._drafts.get(group.id);
    if(!d)return null;
    const rows=name=>d[name].map(r=>({
      slot:Number(r.slotNumber),start:r.start,end:r.end,
      days:[...r.days],percent:Number(r.percent)
    }));
    const payload={
      expected_charge:d.baselineCharge,
      expected_discharge:d.baselineDischarge,
      proposed_charge:rows("charge"),
      proposed_discharge:rows("discharge")
    };
    if(group.id && !group.id.startsWith("sensor."))payload.entry_id=group.id;
    return payload;
  }
  async _saveSchedules(group) {
    // Single user-facing Save action: dry-run against live inverter FIRST,
    // then a single explicit confirmation before all verified writes.
    if(this._previewBusy||this._scheduleWriteBusy||this._modeBusy||this._fallbackBusy)return;
    const current=this._hass?findDevices(this._hass).find(g=>g.id===group.id):null;
    const draft=this._drafts.get(group.id);
    if(!current || !draft?.changed ||
       ![0,1].includes(current.entities.operating_mode?.attributes.raw_mode_code)) {
      this._scheduleWriteFeedback=
        "Save blocked: current mode unsupported or no unsaved edits.";
      this._scheduleWriteError=true;this.render();return;
    }
    await this._planSchedules(group);
    const data=this._fullDraftPayload(group);
    const key=JSON.stringify(data);
    const plan=this._schedulePlan;
    if(!plan || this._schedulePlanKey!==key ||
       plan.status!=="SCHEDULE_PLAN_ONLY" ||
       !Number.isInteger(plan.register_writes_required) ||
       plan.register_writes_required<1) {
      // _planSchedules already surfaced an actionable error/no-change message.
      return;
    }
    await this._applySchedules(group);
  }
  async _planSchedules(group) {
    if(this._previewBusy||this._scheduleWriteBusy||this._modeBusy)return;
    const data=this._fullDraftPayload(group);
    if(!data)return;
    const key=JSON.stringify(data);
    this._previewBusy=true;
    this._schedulePlan=null;
    this._schedulePlanKey="";
    this._scheduleWriteFeedback="Checking complete charge/discharge configuration against inverter…";
    this._scheduleWriteError=false;
    this.render();
    try {
      const answer=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"plan_schedules",service_data:data,return_response:true
      });
      const plan=answer?.response||answer;
      if(plan?.status!=="SCHEDULE_PLAN_ONLY"||plan?.write_sent!==false)
        throw new Error("Backend did not return a safe schedule plan");
      if(JSON.stringify(this._fullDraftPayload(group))!==key)
        throw new Error("Draft changed during validation; validate again");
      this._schedulePlan=plan;
      this._schedulePlanKey=key;
      this._scheduleWriteFeedback=plan.register_writes_required+
        " changed registers planned. No settings changed. "+
        (plan.register_writes_required?
          "Apply is enabled only in Self-consumption mode.":"Already matches inverter.");
      this._scheduleWriteError=false;
    } catch(err) {
      this._schedulePlan=null;
      this._schedulePlanKey="";
      this._scheduleWriteFeedback="Validation blocked: "+
        (err?.message||String(err))+". No writes sent.";
      this._scheduleWriteError=true;
    } finally {
      this._previewBusy=false;this.render();
    }
  }
  async _applySchedules(group) {
    if(this._scheduleWriteBusy||this._modeBusy||this._previewBusy||this._fallbackBusy)return;
    const data=this._fullDraftPayload(group);
    const key=JSON.stringify(data);
    if(!data||key!==this._schedulePlanKey||
        this._schedulePlan?.status!=="SCHEDULE_PLAN_ONLY"||
        this._schedulePlan?.register_writes_required<=0 ||
        ![0,1].includes(group.entities.operating_mode?.attributes.raw_mode_code)){
      this._scheduleWriteFeedback="Save blocked: draft changed or inverter mode unsupported. Check inverter before retrying.";
      this._scheduleWriteError=true;this.render();return;
    }
    if(!window.confirm("LIVE SAJ SCHEDULE WRITES\n\n"+
       "Apply "+this._schedulePlan.register_writes_required+" individual register changes "+
       "across charging/discharging periods?\n\n"+
       "If currently in Time-of-Use, the inverter will temporarily pause to Self-consumption and restore only after verification. "+
       "An interruption may leave PARTIAL settings.\n"+
       "Keep elekeeper open for inspection/recovery. No auto rollback or retries."))return;
    const phrase="I AUTHORIZE TOU SCHEDULE CHANGES";
    this._scheduleWriteBusy=true;
    this._scheduleWriteFeedback="Writing changed registers individually and double-reading after each…";
    this._scheduleWriteError=false;this.render();
    try {
      const answer=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"apply_schedules",service_data:{
          ...data,confirmation:phrase,device_model:"H2-10K-S3-A",
          control_firmware:"v2.018"
        },return_response:true
      });
      const result=answer?.response||answer;
      if(result?.status!=="SCHEDULE_VERIFIED_BY_MODBUS" ||
         result?.write_sent!==true || result?.mode_unchanged!==true ||
         result?.fallback_unchanged!==true)
        throw new Error("Device response not fully verified");
      this._scheduleWriteFeedback=
        "Verified: "+result.registers_written+" registers saved; both schedule "+
        "blocks matched direct Modbus readback. Reopen elekeeper to confirm.";
      this._scheduleWriteError=false;
      this._schedulePlan=null;this._schedulePlanKey="";
      this._drafts.delete(group.id);
      this._schedulePreview.clear();
    } catch(err) {
      this._scheduleWriteFeedback="POSSIBLE PARTIAL WRITE: "+
        (err?.message||String(err))+
        ". DO NOT retry. Check all saved schedule times, days, and power in elekeeper.";
      this._scheduleWriteError=true;
      this._schedulePlan=null;this._schedulePlanKey="";
    } finally {
      this._scheduleWriteBusy=false;this.render();
    }
  }
  choice(options,current,onChange) {
    const select=el("select");
    options.forEach(v=>{const o=el("option",null,v);o.value=v;o.selected=v===current;select.append(o);});
    select.addEventListener("change",e=>onChange(e.target.value));
    return select;
  }
  scheduleSection(group,direction,draft) {
    const title=direction==="charge"?"Charging":"Discharging";
    const rows=draft[direction];
    const state=group.entities[direction+"_schedules"];
    const pane=el("section","pane");
    const header=el("div","top");
    add(header,el("h3",null,title+" · "+rows.length+"/7"),
      el("span","pill",(state?.state||"unavailable")+" on inverter"));
    add(pane,header);
    if (!isValid(state)) add(pane,el("p","bad","Device schedule data unavailable."));
    if (!rows.length) add(pane,el("p","muted","No "+direction+" periods configured."));
    rows.forEach((row,index)=>{
      const container=el("div","slot");
      const bar=el("header");
      const remove=el("button",null,"Remove schedule");
      remove.addEventListener("click",()=>{rows.splice(index,1);draft.changed=true;this.render()});
      add(bar,el("strong",null,title+" "+(index+1)),remove);
      add(container,bar);
      if (row.days.includes("Sat")||row.days.includes("Sun"))
        add(container,el("div","muted","Weekend day-bit mapping is inferred from confirmed Sat+Sun readback."));
      const times=el("div","inputs");
      for (const key of ["start","end"]) {
        const wrapper=el("label","muted",key==="start"?"Start · 24h":"End · 24h");
        const field=el("input","time24");
        // Native time input rejects free-form letters and special characters.
        // en-GB requests a 24-hour hour/minute display in supporting browsers.
        field.type="time";
        field.lang="en-GB";
        field.step="60";
        field.min="00:00";
        field.max="23:59";
        field.required=true;
        field.value=is24Hour(row[key])?row[key]:"00:00";
        field.setAttribute("aria-label",key+" (24-hour HH:MM)");
        field.addEventListener("change",()=>{
          const next=field.value;
          if(!field.validity.valid || !is24Hour(next)){
            field.value=row[key];
            field.setCustomValidity("Choose a valid time between 00:00 and 23:59");
            field.reportValidity();
            field.setCustomValidity("");
            return;
          }
          if (next!==row[key]) {
            row[key]=next;
            draft.changed=true;
            this._schedulePreview.delete(group.id+":"+direction+":"+row.slotNumber);
            this.render();
          }
          field.setCustomValidity("");
        });
        add(wrapper,field);add(times,wrapper);
      }
      add(container,times);
      if (is24Hour(row.start) && is24Hour(row.end) && row.start>row.end) {
        const split=el("button",null,"Split overnight into two schedules");
        split.type="button";
        split.disabled=rows.length>=7 || row.start>="23:59" ||
          row.end<="00:00" || !row.days.length;
        split.title=rows.length>=7?"All seven schedules are already used":
          "Creates a late-night schedule ending 23:59 and next-day schedule starting 00:00";
        split.addEventListener("click",()=>{
          if(rows.length>=7 || row.start>="23:59" ||
             row.end<="00:00" || !row.days.length)return;
          const used=new Set(rows.map(r=>r.slotNumber));
          let nextSlot=1;
          while(used.has(nextSlot)&&nextSlot<=7)nextSlot++;
          if(nextSlot>7)return;
          const following=row.days.map(day=>DAYS[(DAYS.indexOf(day)+1)%7]);
          const second={
            slotNumber:nextSlot,start:"00:00",end:row.end,
            percent:row.percent,dayMask:0,days:[...new Set(following)],
            original:false
          };
          row.end="23:59";
          rows.push(second);
          rows.sort((a,b)=>a.slotNumber-b.slotNumber);
          draft.changed=true;
          this._schedulePreview.clear();
          this.render();
        });
        add(container,split,el("div","muted",
          "Overnight periods use two slots: today until 23:59, next day from 00:00."));
      }
      const actualSlots=(state?.attributes.schedules||[]);
      const saved=actualSlots.find(item => Number(item.slot) === row.slotNumber);
      if (saved) add(container,el("div","saved","Saved on inverter: "+saved.start+"–"+saved.end+" · "+saved.power_percent_raw+"% · "+Number(saved.power_watts_saj_display).toLocaleString()+" W"+(saved.power_conversion_verified ? " (paired)" : " (estimated)")));
      const power=el("div","powerControl");
      const label=el("span","muted",direction==="charge"?"Charging power":"Discharging power");
      const slider=el("input");
      slider.type="range";slider.min="1";slider.max="100";slider.step="1";
      slider.value=String(Math.max(1,row.percent));
      slider.setAttribute("aria-label",(direction==="charge"?"Charging":"Discharging")+" schedule power percentage");
      const percentDisplay=el("strong",null,"");
      const wattDisplay=el("strong",null,"");
      const estimatedLabel=el("span","muted","");
      const inputPercent=el("input","powerPercentInput");
      inputPercent.type="number";inputPercent.min="1";inputPercent.max="100";inputPercent.step="1";
      inputPercent.value=String(row.percent);
      inputPercent.setAttribute("aria-label","Power percentage (1–100)");
      const updatePowerReadout=()=>{
        const percent=row.percent;
        const watts=percent*99;
        percentDisplay.textContent=percent+"%";
        wattDisplay.textContent=watts.toLocaleString()+" W";
        estimatedLabel.textContent=(
          (direction==="charge" ? [50,70] : [50,98,100]).includes(percent)
            ? "elekeeper-paired" : "estimated wattage"
        );
        inputPercent.value=String(percent);
        slider.setAttribute("aria-valuetext",percent+" percent, approximately "+watts+" watts");
      };
      const updatePercent=value=>{
        if(!Number.isInteger(value)||value<1||value>100)return false;
        if(value!==row.percent){
          row.percent=value;
          draft.changed=true;
          this._schedulePreview.delete(group.id+":"+direction+":"+row.slotNumber);
        }
        slider.value=String(value);
        updatePowerReadout();
        return true;
      };
      updatePowerReadout();
      slider.addEventListener("input",()=>updatePercent(Number(slider.value)));
      slider.addEventListener("change",()=>this.render());
      inputPercent.addEventListener("change",()=>{
        if(!updatePercent(Number(inputPercent.value))){
          inputPercent.value=String(row.percent);
          inputPercent.setCustomValidity("Enter a whole percentage between 1 and 100");
          inputPercent.reportValidity();
          inputPercent.setCustomValidity("");
          return;
        }
        this.render();
      });
      const values=el("div","powerValues");
      add(values,label,percentDisplay,el("span","muted","·"),wattDisplay,estimatedLabel);
      add(power,values,slider);
      const exact=el("label","powerExact");
      add(exact,el("span","muted","Set exact %"),inputPercent);
      add(power,exact);
      add(container,power);
      const dayrow=el("div","days");
      DAYS.forEach(day=>{
        const label=el("label","day");
        const cb=el("input");cb.type="checkbox";cb.checked=row.days.includes(day);
        cb.addEventListener("change",()=>{
          row.days=cb.checked ? [...new Set([...row.days,day])] : row.days.filter(d=>d!==day);
          draft.changed=true;
          this._schedulePreview.delete(group.id+":"+direction+":"+row.slotNumber);
          this.render();
        });
        add(label,cb,el("span",null,day));dayrow.append(label);
      });
      add(container,dayrow);
      add(pane,container);
    });
    const addButton=el("button",null,"+ Add "+direction+" schedule");
    addButton.disabled=rows.length>=7;
    addButton.addEventListener("click",()=>{
      if(rows.length>=7)return;
      const used=new Set(rows.map(r=>r.slotNumber));
      let slotNumber=1;
      while(used.has(slotNumber)&&slotNumber<=7)slotNumber++;
      if(slotNumber>7)return;
      rows.push({slotNumber,start:"08:00",end:"08:30",
        percent:50,dayMask:1,days:["Mon"],original:false});
      rows.sort((a,b)=>a.slotNumber-b.slotNumber);
      draft.changed=true;this.render();
    });
    add(pane,addButton);
    return pane;
  }
}
customElements.define(TAG,SajTOUDynamicCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==="saj-tou-dynamic-card")) window.customCards.push({
  type:"saj-tou-dynamic-card",
  name:"SAJ H2 TOU Dynamic",
  description:"Live mode controls and charging/discharging schedule Save with automatic validation and explicit confirmation.",
  preview:true
});
})();
