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
// Prefer the inverter's actual *today* energy counters. Grid import/export
// instead come from the existing gap-aware local monitor ledger because the
// SAJ grid sell/feed-in counter direction is not verified yet.
const nativeTodayEnergy=(hass,key)=>{
  const direct=hass?.states?.["sensor.saj_h2_safe_monitor_"+key+"_today"];
  const values=Object.values(hass?.states||{});
  const friendly={
    solar:"Solar today",
    home:"Home consumed today",
    battery_charge:"Battery charged today",
    battery_discharge:"Battery discharged today"
  }[key];
  const state=direct||values.find(st=>
    st.entity_id?.startsWith("sensor.") &&
    st.attributes?.unit_of_measurement==="kWh" &&
    typeof st.attributes?.friendly_name==="string" &&
    st.attributes.friendly_name.toLowerCase().includes(
      (friendly||"nonexistent marker").toLowerCase()) &&
    /saj|safe monitor/i.test(st.attributes.friendly_name));
  if(!state || ["unknown","unavailable",""].includes(String(state.state)))
    return null;
  const n=Number(state.state);
  return Number.isFinite(n)&&n>=0?n:null;
};
const fmtTodayKwh=value=>
  typeof value==="number"&&Number.isFinite(value)&&value>=0?
    value.toFixed(2)+" kWh":"—";
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
  ".flowTable .flowDailyTotals td{border-top:2px solid var(--divider-color,#52575c);background:rgba(128,128,128,.045);padding:10px 8px;vertical-align:top}",
  ".flowDailyLabel{display:block;font-size:11px;color:var(--secondary-text-color,#aaa);font-weight:700;margin-bottom:7px}",
  ".flowDailyLine{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:5px 0;font-size:12px;line-height:1.4}",
  ".flowDailyLine b{font-variant-numeric:tabular-nums;white-space:nowrap}",
  ".flowDailyName{font-size:11px;color:var(--secondary-text-color,#aaa);text-align:left}",

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

  /* Screenshot-aligned control panel: toolbar action above, inline device
     labels, two matched columns, clear selected mode, compact help text. */
  ".controlPanel{border-radius:15px;background:var(--ha-card-background,var(--card-background-color,#202124))}",
  ".controlPanelHead{padding:14px 20px;min-height:40px;gap:14px;background:rgba(125,125,125,.035)}",
  ".controlPanelHead h3{font-size:17px;font-weight:700;letter-spacing:.1px}",
  ".controlPanelHead .controlRefresh{font-size:13px;padding:9px 13px;border-radius:9px;white-space:nowrap;background:var(--card-background-color,#26282c);border:1px solid var(--divider-color,#505359);transition:border-color .15s ease,background .15s ease}",
  ".controlPanelHead .controlRefresh:hover:not(:disabled){border-color:var(--control-accent);background:rgba(24,173,179,.09)}",
  ".controlCell{padding:22px 20px;display:flex;flex-direction:column;justify-content:flex-start;min-height:145px}",
  ".controlCell+.controlCell{border-left:1px solid var(--divider-color,#45484c)}",
  ".controlSubhead{display:flex;align-items:baseline;column-gap:16px;row-gap:5px;flex-wrap:wrap;margin:0 0 16px}",
  ".controlSubhead h4{font-size:14px;font-weight:700;margin:0;line-height:1.4}",
  ".deviceState{font-size:12px;color:var(--secondary-text-color,#aaa);line-height:1.4}",
  ".controlCell .liveModeButtons{margin:0 0 12px;gap:9px}",
  ".controlCell .liveModeButtons button{min-height:43px;font-size:13px;font-weight:600;border-radius:10px;background:rgba(130,130,130,.035);transition:background .15s ease,border-color .15s ease}",
  ".controlCell .liveModeButtons button:not(:disabled):hover{background:rgba(22,179,190,.075)}",
  ".controlCell .liveModeButtons button[aria-pressed=true]{background:rgba(17,175,185,.12);border:1.5px solid var(--control-accent);box-shadow:inset 0 0 0 1px rgba(20,166,178,.08);opacity:1!important}",
  ".controlCell select{width:min(100%,285px);min-width:0;min-height:43px;border-radius:10px;background:rgba(130,130,130,.035);font-size:13px}",
  ".controlCell p.controlHint{margin:0;color:var(--secondary-text-color,#aaa);font-size:12px;line-height:1.6}",
  ".controlCell p.muted:not(.controlHint){margin-top:12px;color:var(--secondary-text-color,#aaa);font-size:12px;line-height:1.65}",
  ".controlPanel button:focus-visible,.controlPanel select:focus-visible{outline:2px solid var(--control-accent);outline-offset:3px}",
  "@media(max-width:780px){.controlCell{padding:16px;min-height:0}.controlPanelHead{padding:12px 15px}.controlSubhead{margin-bottom:13px}}",
  "@media(max-width:440px){.controlPanelHead{flex-wrap:wrap}.controlPanelHead .controlRefresh{width:100%}.controlCell .liveModeButtons{gap:6px}.controlCell .liveModeButtons button{font-size:12px;padding:10px 6px}}",


  "@media(max-width:650px){.flowGraph{grid-template-columns:repeat(2,minmax(0,1fr))}.flowTable th,.flowTable td{font-size:11px;padding:6px 4px}}",

  /* v0.5.7: manual read-only data refresh next to Last verified. */
  ".readbackBar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 10px;min-height:32px}",
  ".readbackRight{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}",
  ".readbackRefresh{font-size:12px;font-weight:650;min-height:32px;padding:6px 12px;white-space:nowrap;color:var(--primary-text-color,#fff);border:1px solid var(--divider-color,#45484c);background:var(--card-background-color,#25282b);border-radius:8px}",
  ".readbackRefresh:hover:not(:disabled){border-color:var(--control-accent);background:rgba(20,172,184,.09)}",
  ".readbackRefresh:focus-visible{outline:2px solid var(--control-accent);outline-offset:2px}",
  ".readbackNotice{font-size:11px;line-height:1.5;padding:0 0 7px;min-height:12px}",

  /* Native select popups are OS-owned; render the outside-TOU popup inside
     the shadow DOM to guarantee matching dark colors in Brave/Windows. */
  ".controlPanel{overflow:visible}",
  ".fallbackMenu{position:relative;width:min(100%,295px);max-width:100%;z-index:5}",
  ".fallbackTrigger{display:flex;width:100%;min-height:43px;align-items:center;justify-content:space-between;gap:10px;text-align:left;font-size:13px;font-weight:600;padding:10px 13px;border:1px solid var(--divider-color,#50545a);background:var(--card-background-color,#24262a);border-radius:10px;cursor:pointer}",
  ".fallbackMenu.open .fallbackTrigger{border-color:var(--control-accent);box-shadow:0 0 0 1px var(--control-accent)}",
  ".fallbackChevron{font-size:19px;line-height:14px;color:var(--secondary-text-color,#aaa)}",
  ".fallbackOptions{position:absolute;top:calc(100% + 4px);left:0;right:0;padding:5px;border:1px solid var(--divider-color,#4d5155);border-radius:10px;background:var(--card-background-color,#24262a);box-shadow:0 12px 32px rgba(0,0,0,.48);z-index:100;display:flex;flex-direction:column;gap:3px}",
  ".fallbackOptions[hidden]{display:none!important}",
  ".fallbackOption{width:100%;text-align:left;display:block;padding:11px 12px;border:0;border-radius:7px;background:transparent;color:var(--primary-text-color,#f8f8f8);font-size:13px;line-height:1.4;opacity:1!important}",
  ".fallbackOption[aria-selected=true]{background:rgba(14,159,177,.18);color:var(--primary-text-color,#fff);font-weight:700;cursor:default}",
  ".fallbackOption:hover:not(:disabled),.fallbackOption:focus-visible{background:rgba(20,172,184,.14);outline:none}",
  ".fallbackTrigger:disabled{opacity:.55;cursor:not-allowed}",
  /* Condensed battery-first live energy data display (no data/model changes). */
  ".energyOverview{padding:13px 16px 14px;margin:10px 0 14px}",
  ".energyOverview .flowTop{align-items:center;gap:10px}",
  ".energyHeading{display:flex;flex-direction:row;align-items:baseline;gap:14px;flex-wrap:wrap}",
  ".energyHeading h3{font-size:16px}",
  ".energyHeading .muted{font-size:12px}",
  ".energyCadence{font-size:11px;line-height:1.4;color:var(--secondary-text-color,#aaa);white-space:nowrap;font-weight:500}",

  ".socFlow{margin:12px 0 0;padding:0;border:0}",
  ".socFlowTop{font-size:13px;line-height:1.5;margin-bottom:6px}",
  ".socFlowTop span{font-weight:700}",
  ".socFlowTop strong{font-size:13px;font-variant-numeric:tabular-nums}",
  ".socFlow .flowGraphTrack{height:10px}",
  ".flowGraph{gap:12px;margin:11px 0 13px}",
  ".flowGraphCaption{font-size:12px;gap:8px}",
  ".flowGraphCaption b{font-size:13px}",
  ".flowGraphTrack{height:9px}",
  ".flowScroll{margin:0;border-radius:10px}",
  ".flowTable th{padding:8px 5px;font-size:12px}",
  ".flowTable td{padding:7px 5px;font-size:12px}",
  ".flowTable .flowNumbers td{font-size:16px}",
  ".flowSummary{margin-top:9px;font-size:12px}",
  ".flowFoot{margin-top:8px;font-size:11px;line-height:1.45}",
  "@media(max-width:680px){.readbackRight{justify-content:flex-start}.readbackBar{align-items:flex-start}.energyHeading{gap:6px}.energyOverview{padding:12px}.flowGraph{gap:9px}.flowTable{min-width:590px}.flowTable .flowNumbers td{font-size:14px}}",

  /* v0.5.10: current modes in one concise header; no duplicated device labels. */
  ".controlPanelHead{min-height:0;padding:13px 17px;gap:14px;flex-wrap:wrap}",
  ".controlPanelHead h3{font-size:17px;white-space:nowrap}",
  ".controlSummary{display:flex;align-items:center;gap:9px;flex-wrap:wrap;justify-content:flex-end}",
  ".summaryState{display:flex;align-items:baseline;gap:7px;padding:7px 10px;border:1px solid var(--divider-color,#43484c);border-radius:10px;background:rgba(128,128,128,.045);font-size:12px;line-height:1.3;white-space:nowrap}",
  ".sajNav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px;border-bottom:1px solid var(--divider-color,#555);padding-bottom:10px}",
  ".sajNav button[aria-current=page]{border-color:var(--primary-color,#16b9b1);color:var(--primary-text-color,#fff);font-weight:700}",
  ".forecastLink{color:var(--primary-color,#39bace);background:transparent;border:0;text-decoration:underline;cursor:pointer;font:inherit;padding:2px}",
  ".forecastHeader{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin:10px 0 14px}",
  ".forecastStats{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin:12px 0}",
  ".forecastStat{border:1px solid var(--divider-color,#555);border-radius:10px;padding:12px;background:var(--secondary-background-color,transparent)}",
  ".forecastStat b{display:block;font-size:19px;margin-top:7px}",
  ".forecastDays{display:grid;gap:9px;margin:12px 0 18px}",
  ".forecastDay{border-radius:6px;padding:6px;cursor:crosshair}",
  ".forecastDay:focus-visible,.forecastDay:hover{background:rgba(128,128,128,.08);outline:1px solid var(--divider-color,#666)}",
  ".forecastBarTooltip{min-height:26px;font-size:12px;color:var(--secondary-text-color,#bdbdbd);margin:4px 2px 12px;line-height:1.5;font-variant-numeric:tabular-nums}",
  ".forecastHourly,.forecastSettingsShell{border:1px solid var(--divider-color,#444);border-radius:11px;margin:14px 0;overflow:hidden}",
  ".forecastHourly > .forecastDays,.forecastHourly > .forecastBarTooltip{margin:12px 15px}",
  ".forecastSettingsShell > .forecastSettings{border:0;margin:0}",
  ".forecastSvg{max-height:310px;touch-action:pan-y;cursor:crosshair}",

  ".forecastDay{display:grid;grid-template-columns:minmax(75px,120px) 1fr 90px;align-items:center;gap:8px;font-size:12px}",
  ".forecastTrack{height:12px;border-radius:8px;background:var(--divider-color,#444);overflow:hidden}",
  ".forecastFill{height:100%;background:var(--primary-color,#16b9b1);border-radius:8px}",
  ".forecastSettings{margin:18px 0;padding:16px;border:1px solid var(--divider-color,#555);border-radius:12px}",
  ".forecastLearning{padding:13px;margin:12px 0}",
  ".forecastLearning h3{font-size:16px;margin:0 0 10px}",
  ".learningSummary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px}",
  ".learningStat{border:1px solid var(--divider-color,#444);border-radius:9px;padding:10px}",
  ".learningStat strong{display:block;font-size:16px;margin:5px 0}",
  ".learningStat small{font-size:11px;display:block;line-height:1.4}",
  ".learningControls{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px}",
  ".learningSelect{padding:8px;border:1px solid var(--divider-color,#555);border-radius:8px;background:var(--card-background-color,#222);color:var(--primary-text-color,#eee)}",
  ".learningDetails{border-top:1px solid var(--divider-color,#555);margin-top:13px;padding-top:8px}",
  ".learningDetails summary{cursor:pointer;font-size:12px;padding:7px}",
  ".learningDetails p{font-size:12px;line-height:1.55}",

  ".forecastSettingGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:8px;margin:10px 0}",
  ".forecastSettingGrid label{display:flex;flex-direction:column;gap:5px;font-size:12px}",
  ".forecastSettingGrid input{width:100%;box-sizing:border-box}",
  ".costSection{margin:16px 0;padding:18px;border:1px solid var(--divider-color,#555);border-radius:14px;background:var(--card-background-color,#222528)}",
  ".costHeader{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px}",
  ".costHeader h3{font-size:18px;margin:0}",
  ".costStatGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:12px 0}",
  ".costStat{border:1px solid var(--divider-color,#50545a);border-radius:11px;padding:13px;background:rgba(120,120,120,.04)}",
  ".costStat strong{font-size:21px;display:block;letter-spacing:.1px;margin:7px 0;font-variant-numeric:tabular-nums}",
  ".costStat small{font-size:11px;color:var(--secondary-text-color,#aaa);line-height:1.45;display:block}",
  ".costSettings{margin:16px 0;padding:15px;border:1px solid var(--divider-color,#555);border-radius:12px}",
  ".costInputs{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:14px 0}",
  ".costInputs label{font-size:12px;display:flex;flex-direction:column;gap:7px}",
  ".costInputs input{width:100%;box-sizing:border-box}",
  ".costDetail{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:13px}",
  ".costDetail .pane p{margin:6px 0;font-size:12px;line-height:1.5}",
  ".energyGuide{border:1px solid var(--divider-color,#555);border-radius:12px;padding:14px;margin-top:16px}",
  ".energyGuide li{margin-bottom:9px;line-height:1.5;font-size:12px}",
  ".energyGuideCompact{padding:0;overflow:hidden}",
  ".energyGuideCompact .guideSummary{display:flex;justify-content:space-between;align-items:center;gap:12px;cursor:pointer;padding:14px 16px;font-size:13px;list-style-position:inside}",
  ".energyGuideCompact[open] .guideSummary{border-bottom:1px solid var(--divider-color,#444)}",
  ".energyGuideCompact > p{margin:12px 16px}",
  ".guideGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));gap:10px;padding:4px 13px 14px}",
  ".guideGroup{border:1px solid var(--divider-color,#444);border-radius:11px;padding:12px;min-width:0}",
  ".guideGroup h4{margin:0 0 10px;font-size:14px}",
  ".guideItem{padding:8px 0;border-top:1px solid var(--divider-color,#333);min-width:0}",
  ".guideItemTitle{display:block;font-size:12px;font-weight:600;margin-bottom:2px}",
  ".guideFriendly{display:block;color:var(--secondary-text-color,#aaa);font-size:11px;overflow-wrap:anywhere;margin-bottom:5px}",
  ".guideCopyRow{display:flex;align-items:center;gap:6px;min-width:0}",
  ".guideCopyInput{min-width:0;flex:1;width:50px;box-sizing:border-box;user-select:text;-webkit-user-select:text;font-family:monospace;font-size:11px;height:34px;padding:5px 8px}",
  ".guideCopyButton{padding:7px 9px;font-size:11px;min-height:34px;white-space:nowrap}",
  ".guideCopyButton:disabled{opacity:.4}",
  "@media(max-width:520px){.energyGuideCompact .guideSummary{flex-direction:column;align-items:flex-start}.guideGrid{padding:4px 9px 12px}}",
  ".energyEntity{font-size:11px;color:var(--secondary-text-color,#bbb);overflow-wrap:anywhere;display:block}",
  ".costNotice{padding:10px 12px;border-left:3px solid var(--warning-color,#d6ae57);background:rgba(128,128,128,.035);border-radius:0 7px 7px 0;font-size:12px;line-height:1.65;margin:12px 0}",
  ".costPage .costDetail{margin:16px 0 20px}",
  ".costBreakdown,.costEditorShell{border:1px solid var(--divider-color,#464b50);border-radius:12px;margin:14px 0;overflow:hidden}",
  ".costDetailsSummary{padding:14px 16px;cursor:pointer;font-size:13px;font-weight:650}",
  ".costBreakdown[open] > .costDetailsSummary,.costEditorShell[open] > .costDetailsSummary{border-bottom:1px solid var(--divider-color,#45494d)}",
  ".costBreakdown .costDetail,.costBreakdown .costStatGrid{margin:12px;}",
  ".costEditorShell .costSettings{margin:0;border:0;border-radius:0}",
  ".costPage .costStatGrid{grid-template-columns:repeat(auto-fit,minmax(185px,1fr))}",
  ".costPage .costStat strong{font-size:19px}",
  ".costPage .costStat small{max-width:260px}",

  ".costPage .costSettings h3{font-size:17px}",
  ".tariffSubsection{border:1px solid var(--divider-color,#424750);border-radius:12px;padding:15px;margin:18px 0;background:rgba(125,125,125,.025)}",
  ".tariffSubsection h3{margin-bottom:9px}.tariffSubsection .muted{line-height:1.6}",
  ".tariffCategory{border:1px solid var(--divider-color,#444);border-radius:11px;padding:13px;margin:14px 0}",
  ".tariffCategoryHead{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}",
  ".tariffWindow{padding:11px;border:1px solid var(--divider-color,#41454b);border-radius:10px;margin:10px 0;background:rgba(110,110,110,.025)}",
  ".tariffWindowTimes{display:flex;align-items:flex-end;flex-wrap:wrap;gap:10px}",
  ".tariffWindowTimes .tariffField{min-width:130px;flex:1}",
  ".tariffWindowTimes input{min-height:42px}",
  ".tariffField{display:flex;flex-direction:column;gap:7px;font-size:12px;min-width:0}",
  ".tariffField input,.tariffField select{width:100%;box-sizing:border-box;min-height:42px}",
  ".tariffDays{display:flex;gap:7px;flex-wrap:wrap;margin:13px 0 9px}",
  ".tariffDay{display:inline-flex;align-items:center;gap:6px;font-size:12px;border:1px solid var(--divider-color,#45484c);border-radius:9px;padding:7px 9px;cursor:pointer}",
  ".tariffDay input{margin:0;accent-color:var(--primary-color,#16b9b1)}",
  ".tariffPresets{display:flex;gap:6px;flex-wrap:wrap}",
  ".tariffPresets button{font-size:11px;padding:6px 9px}",
  ".tariffAdd{font-size:12px;padding:9px 12px;font-weight:600}",
  ".tariffRemove{font-size:11px;padding:8px 10px;white-space:nowrap}",
  ".tariffTaxGroups{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:15px;margin:14px 0}",
  ".tariffTaxGroup{display:flex;flex-direction:column;align-items:flex-start;gap:7px}",
  ".tariffActions{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0}",
  ".costBandLine{padding-left:9px;border-left:2px solid var(--primary-color,#16b9b1);font-variant-numeric:tabular-nums}",
  ".tariffActive{font-size:12px;font-weight:600;padding:11px 12px;border:1px solid var(--divider-color,#444);border-radius:10px;line-height:1.7;color:var(--primary-text-color,#fff);background:rgba(40,170,190,.045)}",
  "@media(max-width:650px){.tariffSubsection{padding:11px}.tariffCategory{padding:9px}.tariffWindow{padding:9px}.tariffDays{gap:5px}.tariffDay{padding:6px}}",
    ".forecastHistory{border:1px solid var(--divider-color,#555);padding:14px;border-radius:12px;margin-top:16px}",
  ".historyHead{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}",
  ".historyLegend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}",
  ".historyLegend label{font-size:12px;display:flex;align-items:center;gap:5px}",
  ".historyLegend input{accent-color:var(--primary-color,#16b9b1)}",
  ".historySvg{display:block;width:100%;height:auto;max-height:390px;overflow:visible}",
  ".liveHistory{padding:18px 20px;background:var(--ha-card-background,var(--card-background-color,#202124))}",
  ".liveHistory .historyHead h3{font-size:18px;margin:0 0 4px}",
  ".liveHistory .historyLegend{margin:16px 0 14px;gap:10px}",
  ".historyToggle{border:1px solid var(--divider-color,#444);padding:7px 11px;border-radius:10px;cursor:pointer;white-space:nowrap}",
  ".historyToggle input{margin:0}.historyDot{font-size:15px}",
  "@media(max-width:650px){.liveHistory{padding:12px}.historyToggle{padding:6px 8px}.liveHistory .historyLegend{gap:6px}}",
  ".historySvg{touch-action:pan-y;cursor:crosshair;outline-offset:3px}",
  ".historyTooltip{display:flex;flex-wrap:wrap;gap:7px 17px;align-items:center;padding:10px 12px;margin-top:6px;border:1px solid var(--divider-color,#45484c);border-radius:9px;background:var(--secondary-background-color,rgba(128,128,128,.06));font-size:12px;min-height:44px}",
  ".historyTooltip strong{font-size:13px;margin-right:3px}",
  ".historyTooltip .historyValue{white-space:nowrap;font-variant-numeric:tabular-nums}",
  ".historyTooltip .historyEmpty{color:var(--secondary-text-color,#aaa)}",
    ".historyFoot{font-size:11px;color:var(--secondary-text-color,#aaa);margin-top:8px;line-height:1.5}",
  ".forecastNotice{padding:10px;border-left:3px solid var(--warning-color,#d3a435);margin:10px 0;font-size:12px;line-height:1.6}",
    ".summaryLabel{color:var(--secondary-text-color,#aaa);font-weight:500}",
  ".summaryState strong{color:var(--primary-text-color,#fff);font-weight:700;font-variant-numeric:tabular-nums}",
  ".controlCell{padding:14px 18px 15px;min-height:0}",
  ".controlSubhead{margin:0 0 11px}",
  ".controlSubhead h4{font-size:14px}",
  ".controlCell .liveModeButtons{margin:0 0 9px}",
  ".controlCell p.controlHint,.controlCell p.muted:not(.controlHint){font-size:11px;line-height:1.5}",
  /* Schedules use a shallow header+action row, not a 7-slot empty-state box. */
  ".scheduleTitle{margin:14px 0 7px}",
  ".scheduleTitle h3{font-size:16px}",
  ".scheduleGrid{gap:10px;margin:0}",
  ".scheduleGrid .pane{padding:12px 15px;border-radius:12px;min-height:0}",
  ".scheduleGrid .pane .top{gap:10px}",
  ".scheduleGrid .pane .top h3{font-size:15px;margin:0}",
  ".scheduleGrid .pane .addSchedule{background:transparent;border-color:var(--divider-color,#52565c);font-size:12px;font-weight:600;padding:7px 11px;min-height:33px}",
  ".scheduleGrid .pane .addSchedule:hover:not(:disabled){border-color:var(--control-accent);background:rgba(22,169,185,.075)}",
  ".emptySchedule{padding:7px 0 1px;margin:7px 0 0;font-size:12px}",
  ".scheduleGrid .slot{padding:11px 0 7px}",
  ".scheduleActions{margin:10px 0 3px;gap:8px;display:flex;justify-content:space-between}",
  ".scheduleActions button{font-size:12px;padding:9px 12px;min-height:37px}",
  ".scheduleActions .primaryAction{margin-left:auto}",
  ".scheduleFootnote{font-size:11px;line-height:1.5;color:var(--secondary-text-color,#aaa);margin:7px 1px 0}",
  ".draftNotice{border-left:2px solid var(--warning-color,#d6ae57);padding:5px 9px;font-size:12px;color:var(--secondary-text-color,#bbb);margin-top:9px}",
  ".unsavedPill{font-size:11px;color:var(--warning-color,#e1b663);font-weight:650}",
  "@media(max-width:850px){.controlPanelHead{align-items:flex-start}.controlSummary{justify-content:flex-start}.summaryState{padding:6px 8px;font-size:11px}}",
  "@media(max-width:520px){.scheduleGrid .pane{padding:11px 12px}.scheduleActions{flex-wrap:wrap}.scheduleActions button{flex:1}.controlPanelHead h3{width:100%}.summaryState{white-space:normal}.controlSummary{width:100%}}",



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
    this._lastForecastSignature = "";
    this._modeBusy = false;
    this._fallbackBusy = false;
    this._fallbackFeedback = "";
    this._fallbackFeedbackError = false;
    this._modeFeedback = "";
    this._modeFeedbackError = false;
    this._modeBusyEntry = "";
    this._refreshBusy = false;
    this._refreshNotice = "";
    this._refreshNoticeError = false;
    this._schedulePreview = new Map();
    this._previewBusy = false;
    this._scheduleWriteBusy = false;
    this._scheduleWriteFeedback = "";
    this._scheduleWriteError = false;
    this._schedulePlan = null;
    this._schedulePlanKey = "";
    this._page = "control";
    this._costForm = null;
    this._costEditing = false;
    this._costEditorOpen = null;
    this._costBreakdownOpen = false;
    this._costSaving = false;
    this._costMessage = "";
    this._costError = false;
    this._forecastForm = null;
    this._forecastEditorOpen = null;
    this._forecastSaving = false;
    this._forecastScanBusy = false;
    this._forecastScanDays = 180;
    this._forecastScanMessage = "";
    this._forecastMessage = "";
    this._forecastError = false;
    this._historyData = null;
    this._historyPending = false;
    this._historyError = "";
    this._historyHours = 24;
    this._historyVisible = {solar:true,home:true,battery:true,grid:true};
    this._historySignature = "";
    this._forecastHistoryData = null;
    this._forecastHistoryPending = false;
    this._forecastHistoryError = "";
    this._forecastHistoryDate = "";
    this._forecastHistoryFetchedAt = 0;
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
    const forecastSig=this._forecastState()?.last_updated||"";
    const costSig=this._costState()?.last_updated||"";
    const forecastChanged=forecastSig!==this._lastForecastSignature;
    this._lastForecastSignature=forecastSig;
    const combinedEnergySig=energySig+"|"+forecastSig+"|"+costSig;
    if (sig!==this._lastSignature) {
      this._lastSignature=sig;
      this._lastEnergySignature=combinedEnergySig;
      // Follow external elekeeper changes unless the user is editing a draft.
      devices.forEach(g=>{
        const existing=this._drafts.get(g.id);
        if (existing && !existing.changed) this._drafts.set(g.id,cloneDraft(g));
      });
      this.render();
    } else if(combinedEnergySig!==this._lastEnergySignature) {
      this._lastEnergySignature=energySig;
      // Updating safe monitoring graphics must not reset an active time input
      // or discard an in-progress TOU schedule draft.
      if(this._page==="forecast"||this._page==="cost"){
        // Preserve focused editable settings while live telemetry refreshes.
        if(this._page==="forecast"&&forecastChanged&&!this._forecastSaving)this.render();
        if(this._page==="cost"&&!this._costEditing&&
           !this._costEditorOpen&&!this._costSaving)this.render();
      }else{
        const old=this.shadowRoot?.querySelector(".energyOverview");
        if(old)old.replaceWith(this._energyOverview());
        else this.render();
      }
    }
  }
  _goPage(page){
    this._page=page;
    this.render();
  }
  _costState(){
    if(!this._hass?.states)return null;
    const entries=Object.values(this._hass.states).filter(s=>
      s.attributes?.saj_tou_role==="cost_estimate");
    return entries.find(s=>s.attributes.saj_tou_entry_id===this._selected)
      ||entries[0]||null;
  }
  _currency(value){
    if(typeof value!=="number"||!Number.isFinite(value))return "—";
    const currency=this._costState()?.attributes?.pricing?.currency||"AUD";
    return new Intl.NumberFormat("en-AU",{
      style:"currency",currency,minimumFractionDigits:2,
      maximumFractionDigits:2}).format(value);
  }
  _costOverview(){
    const section=el("section","costSection");
    const head=el("div","costHeader");
    const heading=el("div");
    add(heading,el("h3",null,"Cost estimates"),
      el("span","muted","Electricity import, export and standing charges"));
    const detail=el("button","secondaryAction","View costs & settings ›");
    detail.type="button";
    detail.addEventListener("click",()=>this._goPage("cost"));
    add(head,heading,detail);
    add(section,head);
    const state=this._costState();
    const settings=state?.attributes?.pricing||{};
    if(!state){
      add(section,el("div","costNotice",
        "Energy accounting is unavailable. Configure SAJ H2 Safe Monitor using the same inverter IP, then reload this integration. No tariff or grid energy is being guessed."));
      return section;
    }
    const active=state.attributes.current_tariff;
    if(active?.import && active?.export){
      add(section,el("p","tariffActive",
        "Active now · Import: "+active.import.name+" ("+
        this._currency(active.import.rate)+"/kWh) · Export: "+
        active.export.name+" ("+this._currency(active.export.rate)+"/kWh)"+
        (active.export.high_window&&active.export.id!=="high"?
          " · special high-FiT origin not verified":"")));
    }
    if(!settings.configured)
      add(section,el("div","costNotice",
        "Example prices are not your tariff. Open Costs & savings to configure peak, off-peak, solar sponge, export FiT windows and GST."));
    const today=state.attributes.today,month=state.attributes.month;
    const stats=el("div","costStatGrid");
    for(const [label,row,note] of [
      ["Today (tracked)",today,"Full daily supply + measured electricity"],
      ["This month (tracked)",month,"One daily supply charge per tracked day"]
    ]){
      const card=el("div","costStat");
      add(card,el("span","muted",label),
        el("strong",null,settings.configured&&row?
          this._currency(row.net_cost):"—"),
        el("small",null,note+" · "+(row?
          (row.coverage_seconds/3600).toFixed(1)+" hours monitored":
          "recordings pending")));
      stats.append(card);
    }
    add(section,stats);
    add(section,el("p","historyFoot",
      "The full daily supply charge is included once per monitored calendar day, even with no energy readings. "+
      "Import/export charges cover recorded intervals only; this is not a retailer bill."));
    return section;
  }
  _tariffDefault(legacy){
    const every=[0,1,2,3,4,5,6];
    return {
      version:1,configured:false,currency:legacy.currency||"AUD",
      default_import_rate:Number(legacy.import_rate??0.35),
      import_bands:[
        {id:"peak",name:"Peak",rate:0.52,windows:[
          {start:"07:00",end:"09:00",days:[...every]},
          {start:"17:00",end:"21:00",days:[...every]}]},
        {id:"offpeak",name:"Off-peak",rate:0.24,windows:[
          {start:"21:00",end:"07:00",days:[...every]}]},
        {id:"sponge",name:"Solar sponge",rate:0.12,windows:[
          {start:"10:00",end:"15:00",days:[...every]}]}
      ],
      export_standard_rate:Number(legacy.export_rate??0.05),
      export_standard_windows:[],
      export_fallback_rate:Number(legacy.export_rate??0.05),
      export_high_rate:0.25,
      export_high_windows:[{start:"17:00",end:"21:00",days:[...every]}],
      high_fit_eligibility:"battery_only_unverified",
      daily_supply:Number(legacy.daily_supply??1),
      gst_percent:10,gst_mode:"included",
      gst_on_import:true,gst_on_export:false,gst_on_supply:true,
      other_tax_percent:0,
      other_tax_on_import:true,other_tax_on_export:false,
      other_tax_on_supply:true
    };
  }
  _refreshTariffEditor(){
    const old=this.shadowRoot?.querySelector(".costPage");
    if(old)old.replaceWith(this._costPage());
    else this.render();
  }
  _costText(label,kind,row){
    const stat=el("div","costStat");
    add(stat,el("span","muted",label),
      el("strong",null,typeof row?.[kind]==="number"?
        this._currency(row[kind]):"—"));
    return stat;
  }
  _costPage(){
    const root=el("section","costPage");
    const header=el("div","forecastHeader");
    add(header,el("h2",null,"Costs & savings"),
      el("span","muted","Time-of-use prices · estimates from recorded energy"));
    add(root,header);
    const state=this._costState();
    if(!state){
      add(root,el("p","costNotice",
        "SAJ H2 Safe Monitor must be installed and configured using the same inverter before accounting can be shown. Configure it and reload this controller; no prices or inverter settings will be guessed."));
      return root;
    }
    const data=state.attributes;
    const pricing=data.pricing||{};
    const active=data.current_tariff;
    if(active?.import && active?.export){
      add(root,el("p","tariffActive",
        "Current import · "+active.import.name+" at "+
        this._currency(active.import.rate)+"/kWh  · Current export · "+
        active.export.name+" at "+this._currency(active.export.rate)+"/kWh"+
        (active.export.high_window&&active.export.id!=="high"?
          " (special high-FiT window: eligibility unverified)":"")));
    }
    const isTOU=Boolean(pricing.tariff_profile?.configured);
    if(this._costEditorOpen===null)this._costEditorOpen=!isTOU;
    if(!isTOU){
      add(root,el("p","costNotice",
        "Time-of-use example schedules are shown below. They are NOT your retailer's rates. "+
        (pricing.configured?
          "Your previous flat rate is still in use until you save a tariff schedule. ":
          "No actual electricity prices have been confirmed yet. ")+
        "Check your bill or plan factsheet, set every applicable time window and tax rule, then save."));
    }else{
      add(root,el("p","muted",
        "Import/export rates apply to electricity as it is measured. "+
        "A full daily supply charge is posted once for each tracked local calendar day, regardless of monitoring gaps. "+
        "Changing a tariff preserves accumulated costs, and does not charge the same day's supply fee again."));
    }
    const stats=el("div","costStatGrid");
    for(const [name,key,row,small] of [
      ["Today · estimated net","net_cost",data.today,"Covered intervals only"],
      ["Month · estimated net","net_cost",data.month,"Covered intervals only"],
      ["Today · self-supply / export benefit","self_supply_estimated_benefit",
        data.today,"Illustrative value, not verified battery savings"]
    ]){
      const item=this._costText(name,key,pricing.configured?row:null);
      add(item,el("small",null,small));stats.append(item);
    }
    add(root,stats);
    const detail=el("div","costDetail");
    for(const [heading,row] of [["Today · monitored",data.today],
                                 ["This month · monitored",data.month]]){
      const card=el("div","pane");
      add(card,el("h3",null,heading));
      if(!row){
        add(card,el("p","muted","No recorded readings for this period yet."));
      }else{
        for(const [label,key,unit] of [
          ["Grid imported","import_kwh","energy"],
          ["Grid exported","export_kwh","energy"],
          ["Import charge incl. applicable tax","import_cost","money"],
          ["Export payment / fee incl. applicable tax","export_credit","money"],
          ["Supply charge incl. applicable tax","supply_cost","money"],
          ["Full daily supply fees counted","supply_days_charged","days"],
          ["Additional tax adjustment (already included)","tax_adjustment","money"],
          ["High-FiT potential adjustment (not credited)","high_fit_unverified_difference","money"]
        ]){
          if(key==="high_fit_unverified_difference"&&
             typeof row[key]!=="number")continue;
          const value=row[key];
          const rendered=typeof value!=="number"?"—":unit==="energy"?
            value.toFixed(3)+" kWh":unit==="days"?
            value.toFixed(0)+" day(s)":this._currency(value);
          add(card,el("p",null,label+": "+rendered));
        }
        add(card,el("p","muted",
          "Energy coverage: "+(Number(row.coverage_seconds||0)/3600).toFixed(1)+
          " h · Tariff-priced coverage: "+
          (Number(row.tariff_coverage_seconds||0)/3600).toFixed(1)+
          " h. Fixed supply is charged per day, separately from recorded energy."));
        if(row.label)add(card,el("p","muted",row.label));
        for(const [heading,key] of [
          ["Import rate breakdown","import_bands"],
          ["Export FiT breakdown","export_bands"]
        ]){
          const entries=Array.isArray(row[key])?row[key]:[];
          if(entries.length){
            add(card,el("h4",null,heading));
            for(const entry of entries){
              add(card,el("p","costBandLine",
                entry.label+": "+(Number(entry.kwh)||0).toFixed(3)+
                " kWh · "+this._currency(Number(entry.amount)||0)));
            }
          }
        }
      }
      detail.append(card);
    }
    const breakdown=el("details","costBreakdown");
    breakdown.open=Boolean(this._costBreakdownOpen);
    breakdown.addEventListener("toggle",()=>this._costBreakdownOpen=breakdown.open);
    add(breakdown,el("summary","costDetailsSummary",
      "Cost breakdown · Imported, exported, supply and rates"));
    const secondary=el("div","costStatGrid");
    for(const [label,value,description] of [
      ["Month · self-supply / export value",data.month?.self_supply_estimated_benefit,
        "Illustrative combined benefit"],
      ["Today · battery discharge potential",data.today?.battery_discharge_illustrative_value,
        "Overlaps self-supply benefit; not additional bill saving"]
    ]){
      const card=this._costText(label,"amount",
        {amount:pricing.configured?value:null});
      add(card,el("small",null,description));secondary.append(card);
    }
    add(breakdown,secondary,detail);
    add(root,breakdown);
    if(!this._costForm){
      const source=pricing.tariff_profile||this._tariffDefault(pricing);
      this._costForm=JSON.parse(JSON.stringify(source));
    }
    const p=this._costForm;
    const currency=pricing.currency||this._hass?.config?.currency||"AUD";
    const editorShell=el("details","costEditorShell");
    editorShell.open=Boolean(this._costEditorOpen);
    editorShell.addEventListener("toggle",()=>{
      this._costEditorOpen=editorShell.open;
      this._costEditing=editorShell.open;
    });
    add(editorShell,el("summary","costDetailsSummary",
      "Edit electricity tariffs · Time windows, export FiT & GST"));
    const editor=el("section","costSettings");
    add(editor,el("h3",null,"Your time-of-use electricity plan"),
      el("p","muted",
        "Configure your electricity plan by local weekday and time. "+
        "Each import rate can have several separate periods, including morning and evening peaks. "+
        "Overnight windows (e.g. 21:00–07:00) automatically cross midnight; selected weekdays mean the day the window STARTS. "+
        "All rates can be positive or negative."));
    const field=(label,value,onChange,{step="0.001",min="-100",max="100",type="number"}={})=>{
      const holder=el("label","tariffField");
      add(holder,el("span",null,label));
      const input=el("input");
      input.type=type;
      if(type==="number"){input.step=step;input.min=min;input.max=max;}
      input.value=String(value);
      input.addEventListener("input",()=>{
        const next=type==="number"?
          (input.value===""?null:Number(input.value)):input.value;
        onChange(next);
        this._costEditing=true;
      });
      holder.append(input);
      return holder;
    };
    const control=(text,onClick,className="")=>{
      const b=el("button",className,text);
      b.type="button";
      b.addEventListener("click",()=>{this._costEditing=true;onClick();});
      return b;
    };
    const daysShort=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    const windowView=(window,windows,index,label)=>{
      const container=el("div","tariffWindow");
      const times=el("div","tariffWindowTimes");
      add(times,
        field("From",window.start,v=>window.start=v,{type:"time"}),
        field("To",window.end,v=>window.end=v,{type:"time"}));
      const remove=control("Remove time",()=>{
        windows.splice(index,1);this._refreshTariffEditor();
      },"tariffRemove");
      remove.disabled=windows.length<=1 &&
        windows!==p.export_high_windows && windows!==p.export_standard_windows;
      add(times,remove);add(container,times);
      const days=el("div","tariffDays");
      days.setAttribute("aria-label",label+" weekdays");
      daysShort.forEach((day,d)=>{
        const item=el("label","tariffDay");
        const check=el("input");
        check.type="checkbox";check.checked=window.days.includes(d);
        check.addEventListener("change",()=>{
          window.days=check.checked?
            [...new Set([...window.days,d])].sort((a,b)=>a-b):
            window.days.filter(v=>v!==d);
          this._costEditing=true;
        });
        add(item,check,el("span",null,day));days.append(item);
      });
      add(container,days);
      const quick=el("div","tariffPresets");
      for(const [title,selected] of [
        ["Every day",[0,1,2,3,4,5,6]],
        ["Weekdays",[0,1,2,3,4]],
        ["Weekend",[5,6]]
      ]){
        add(quick,control(title,()=>{
          window.days=[...selected];this._refreshTariffEditor();
        }));
      }
      add(container,quick);
      return container;
    };
    const imports=el("section","tariffSubsection");
    add(imports,el("h3",null,"1. Grid import prices"),
      el("p","muted",
        "Fallback applies to any local time not covered by a category. "+
        "Two import categories cannot overlap on the same weekday; overlapping times are rejected on Save."));
    const fallback=el("div","costInputs");
    add(fallback,field("Other / fallback ("+currency+"/kWh)",
      p.default_import_rate,v=>p.default_import_rate=v));
    add(imports,fallback);
    p.import_bands.forEach((band,i)=>{
      const category=el("div","tariffCategory");
      const head=el("div","tariffCategoryHead");
      add(head,el("strong",null,"Rate category "+(i+1)),
        control("Remove category",()=>{
          p.import_bands.splice(i,1);this._refreshTariffEditor();
        },"tariffRemove"));
      add(category,head);
      const fields=el("div","costInputs");
      add(fields,
        field("Category name",band.name,v=>band.name=v,{type:"text"}),
        field("Import price ("+currency+"/kWh)",band.rate,v=>band.rate=v));
      add(category,fields);
      band.windows.forEach((w,j)=>category.append(windowView(
        w,band.windows,j,band.name+" window "+(j+1))));
      const addWindow=control("+ Another time window",()=>{
        if(band.windows.length>=24)return;
        band.windows.push({start:"12:00",end:"14:00",days:[0,1,2,3,4,5,6]});
        this._refreshTariffEditor();
      },"tariffAdd");
      addWindow.disabled=band.windows.length>=24;
      add(category,addWindow);imports.append(category);
    });
    const addCategory=control("+ Add import rate category",()=>{
      const existing=new Set(p.import_bands.map(b=>b.id));
      let i=1;while(existing.has("custom"+i))i++;
      p.import_bands.push({id:"custom"+i,name:"Extra rate "+i,
        rate:p.default_import_rate,
        windows:[{start:"12:00",end:"13:00",days:[0,1,2,3,4,5,6]}]});
      this._refreshTariffEditor();
    },"tariffAdd");
    addCategory.disabled=p.import_bands.length>=12;
    add(imports,addCategory);
    add(editor,imports);
    const exports=el("section","tariffSubsection");
    add(exports,el("h3",null,"2. Grid exports & battery high FiT"),
      el("p","muted",
        "Standard FiT applies whenever a special export window does not qualify. "+
        "A higher payment intended only for battery exports cannot reliably be distinguished from solar exports with current sensors."));
    const exportFields=el("div","costInputs");
    add(exportFields,
      field("Standard export FiT ("+currency+"/kWh)",
        p.export_standard_rate,v=>p.export_standard_rate=v),
      field("Special / battery high FiT ("+currency+"/kWh)",
        p.export_high_rate,v=>p.export_high_rate=v),
      field("Other export fallback ("+currency+"/kWh)",
        p.export_fallback_rate,v=>p.export_fallback_rate=v));
    add(exports,exportFields);
    add(exports,el("h4",null,"Standard FiT times"),
      el("p","muted",
        "With no standard windows, the standard FiT applies at every time except qualifying high-FiT windows. "+
        "Add standard windows to restrict it; other times then use the separate 'Other export fallback' rate."));
    const standardWindows=el("div","tariffStandardWindows");
    p.export_standard_windows.forEach((w,i)=>
      standardWindows.append(windowView(w,p.export_standard_windows,i,
        "Standard FiT window "+(i+1))));
    const addStandard=control("+ Add standard FiT window",()=>{
      p.export_standard_windows.push({
        start:"00:00",end:"07:00",days:[0,1,2,3,4,5,6]
      });
      this._refreshTariffEditor();
    },"tariffAdd");
    addStandard.disabled=p.export_standard_windows.length>=24;
    add(exports,standardWindows,addStandard);
    add(exports,el("h4",null,"Special high-FiT times"));
    const eligibility=el("label","tariffField");
    add(eligibility,el("span",null,"Which exports qualify for the high FiT?"));
    const eligible=el("select");
    for(const [key,name] of [
      ["battery_only_unverified",
        "Battery-only / unverified — use standard FiT; show potential high credit"],
      ["all_exports",
        "All exports during the high-FiT window — my retailer confirms this"]
    ]){
      const option=el("option",null,name);
      option.value=key;option.selected=p.high_fit_eligibility===key;
      eligible.append(option);
    }
    eligible.addEventListener("change",()=>{
      p.high_fit_eligibility=eligible.value;this._costEditing=true;
    });
    add(eligibility,eligible);
    add(exports,eligibility);
    add(exports,el("p","costNotice",
      "If the higher rate is battery-only, this integration cannot certify the exported source. "+
      "It conservatively bills at the standard FiT and reports a possible high-FiT adjustment separately. "+
      "Choose 'All exports' only when your retailer contract explicitly allows it."));
    const highWindows=el("div","tariffHighWindows");
    p.export_high_windows.forEach((window,i)=>{
      highWindows.append(windowView(window,p.export_high_windows,i,"High FiT window "+(i+1)));
    });
    if(!p.export_high_windows.length)
      add(highWindows,el("p","muted","No high-FiT window: all exports use the standard rate."));
    const addHigh=control("+ Add special FiT window",()=>{
      p.export_high_windows.push({
        start:"17:00",end:"21:00",days:[0,1,2,3,4,5,6]
      });
      this._refreshTariffEditor();
    },"tariffAdd");
    addHigh.disabled=p.export_high_windows.length>=24;
    add(exports,highWindows,addHigh,el("p","muted",
      "Export FiT windows can overlap with import windows because they apply to different meter directions."));
    add(editor,exports);
    const taxes=el("section","tariffSubsection");
    add(taxes,el("h3",null,"3. Supply charge, GST & other taxes"));
    const taxFields=el("div","costInputs");
    add(taxFields,
      field("Daily supply charge ("+currency+"/day)",p.daily_supply,v=>p.daily_supply=v),
      field("GST (%)",p.gst_percent,v=>p.gst_percent=v,
        {step:"0.1",min:"0",max:"100"}),
      field("Extra levy (+) or rebate (−) (%)",p.other_tax_percent,
        v=>p.other_tax_percent=v,{step:"0.1",min:"-100",max:"100"}));
    add(taxes,taxFields);
    const gstMode=el("label","tariffField");
    add(gstMode,el("span",null,"Are entered prices GST-inclusive?"));
    const selectGST=el("select");
    for(const [value,label] of [
      ["included","GST already included — do not add GST again"],
      ["exclusive","GST exclusive — add GST on selected charges / credits"]
    ]){
      const option=el("option",null,label);
      option.value=value;option.selected=p.gst_mode===value;
      selectGST.append(option);
    }
    selectGST.addEventListener("change",()=>{
      p.gst_mode=selectGST.value;this._costEditing=true;
    });
    add(gstMode,selectGST);
    add(taxes,gstMode);
    const taxable=el("div","tariffTaxGroups");
    for(const [heading,prefix] of [
      ["GST applied to","gst_on_"],
      ["Extra tax / levy applied to","other_tax_on_"]
    ]){
      const group=el("div","tariffTaxGroup");
      add(group,el("strong",null,heading));
      for(const [fieldName,label] of [
        ["import","Grid import charges"],
        ["export","Grid export FiT or fee"],
        ["supply","Daily supply charge"]
      ]){
        const k=prefix+fieldName;
        const holder=el("label","tariffDay");
        const checkbox=el("input");
        checkbox.type="checkbox";checkbox.checked=Boolean(p[k]);
        checkbox.addEventListener("change",()=>{
          p[k]=checkbox.checked;this._costEditing=true;
        });
        add(holder,checkbox,el("span",null,label));group.append(holder);
      }
      add(taxable,group);
    }
    add(taxes,taxable,el("p","muted",
      "Defaults assume Australian residential GST is included on import and supply and not applied to ordinary feed-in payments. "+
      "Confirm your contract and taxation circumstances. Extra levy/rebate is applied on top; enter negative percentages for a rebate. Signed rates and fees remain supported."));
    add(editor,taxes);
    const actionRow=el("div","tariffActions");
    const save=el("button","primaryAction",
      this._costSaving?"Validating & saving…":"Save complete electricity tariff");
    save.type="button";save.disabled=this._costSaving;
    save.addEventListener("click",()=>this._saveCostSettings());
    const reset=control("Discard unsaved changes",()=>{
      this._costForm=null;this._costEditing=false;this._costMessage="";
      this._costEditorOpen=false;
      this._refreshTariffEditor();
    });
    add(actionRow,save,reset);add(editor,actionRow);
    if(this._costMessage)
      add(editor,el("p",this._costError?"bad":"okay",this._costMessage));
    add(editor,el("p","historyFoot",
      "Static TOU rates only; dynamic retailer/AEMO pricing not connected. "+
      "Tariff saves do not change inverter operating mode, battery or charge schedules. "+
      "Historic cost entries are not re-priced; a new tariff version applies to future readings."));
    add(editorShell,editor);
    add(root,editorShell);
    add(root,el("div","costNotice",
      "Estimated grid direction must first be checked against your meter. "+
      "Today/month figures cover recorded intervals only, and will not exactly match a retailer bill. "+
      "Battery-discharge potential overlaps self-consumption benefit and does not deduct charging costs."));
    add(root,this._energySetupGuide());
    return root;
  }
  async _saveCostSettings(){
    const profile=this._costForm;
    if(!profile){this._costMessage="No tariff settings to save.";this._costError=true;return;}
    const numeric=[
      profile.default_import_rate,profile.export_standard_rate,
      profile.export_fallback_rate,profile.export_high_rate,
      profile.daily_supply,profile.gst_percent,
      profile.other_tax_percent,...profile.import_bands.map(b=>b.rate)
    ];
    if(numeric.some(n=>typeof n!=="number"||!Number.isFinite(n))){
      this._costMessage="Enter valid numbers in every rate and tax input.";
      this._costError=true;this._refreshTariffEditor();return;
    }
    if(!profile.import_bands.every(b=>b.name.trim()&&b.windows.length &&
       b.windows.every(w=>w.days?.length&&w.start!==w.end)) ||
       !profile.export_high_windows.every(w=>w.days?.length&&w.start!==w.end) ||
       !profile.export_standard_windows.every(w=>w.days?.length&&w.start!==w.end)){
      this._costMessage="Check category names, start/end times and selected weekdays.";
      this._costError=true;this._refreshTariffEditor();return;
    }
    this._costSaving=true;this._costMessage="";this._costError=false;
    this._refreshTariffEditor();
    try{
      const data={profile_json:JSON.stringify({...profile,configured:true})};
      if(this._selected&&!this._selected.startsWith("sensor."))
        data.entry_id=this._selected;
      const response=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"save_tariff_profile",service_data:data,return_response:true
      });
      this._costForm=null;
      this._costEditing=false;
      this._costEditorOpen=false;
      this._costMessage="Tariff saved. The new schedule applies to future monitored intervals only; previous costs remain unchanged.";
      this._costError=false;
    }catch(error){
      this._costMessage="Could not save tariff: "+(error?.message||String(error));
      this._costError=true;
    }finally{
      this._costSaving=false;this._refreshTariffEditor();
    }
  }
  _copyEntityId(value,button){
    if(!value)return;
    const feedback=(ok)=>{
      button.textContent=ok?"Copied ✓":"Select the ID";
      button.title=ok?"Copied to clipboard":"Select the ID in the field and copy it";
      // Do not add persistent timers or listeners; the message is temporary
      // until a normal HA dashboard render or the next click.
    };
    const fallback=()=>{
      const input=button.parentElement?.querySelector("input");
      if(input){input.focus();input.select();}
      try{if(document.execCommand("copy"))feedback(true);else feedback(false);}
      catch(_){feedback(false);}
    };
    if(navigator.clipboard?.writeText){
      navigator.clipboard.writeText(value).then(()=>feedback(true),fallback);
    }else fallback();
  }
  _energySetupGuide(){
    // Compact by default, but every ID is a real HA entity_id. Never
    // manufacture names by slugifying the human-friendly labels.
    const guide=el("details","energyGuide energyGuideCompact");
    const heading=el("summary","guideSummary");
    add(heading,el("strong",null,"Home Assistant Energy · Sensor IDs & copy"),
      el("span","muted","Grid · Solar · Battery · Home"));
    add(guide,heading);
    add(guide,el("p","muted",
      "Choose sensors under Settings → Dashboards → Energy. "+
      "Each field below contains the actual Home Assistant entity ID; "+
      "click the field to select it, or use Copy. W is live power; kWh is energy over time."));
    const all=Object.values(this._hass?.states||{});
    const owned=all.filter(v=>v.attributes?.saj_energy_role||
      v.attributes?.saj_tou_role==="editable_forecast");
    const match=(key)=>{
      if(key==="editable_forecast"){
        return owned.find(v=>v.attributes?.saj_tou_role==="editable_forecast"&&
          (!this._selected||v.attributes?.saj_tou_entry_id===this._selected))||
          owned.find(v=>v.attributes?.saj_tou_role==="editable_forecast");
      }
      return owned.find(v=>v.attributes?.saj_energy_role===key&&
        (!this._selected||v.attributes?.saj_tou_entry_id===this._selected))||
        owned.find(v=>v.attributes?.saj_energy_role===key);
    };
    const groups=[
      ["Grid · Electricity",[
        ["Imported energy · kWh","grid_import_energy_estimate"],
        ["Exported energy · kWh","grid_export_energy_estimate"],
        ["Signed power · W (Standard)","grid_signed_power"],
        ["Imported power · W (Two sensors)","grid_import_power"],
        ["Exported power · W (Two sensors)","grid_export_power"]
      ]],
      ["Solar",[
        ["Solar energy · kWh","solar_production_energy"],
        ["Solar power · W","solar_production_power"],
        ["Solar forecast · kWh (not a meter)","editable_forecast"]
      ]],
      ["Battery",[
        ["Energy charged · kWh","battery_charged_energy"],
        ["Energy discharged · kWh","battery_discharged_energy"],
        ["State of charge · %","battery_state_of_charge"],
        ["Signed power · W","battery_power"]
      ]],
      ["Home",[
        ["Home consumption · kWh","home_consumption_energy"],
        ["Home power · W","home_consumption_power"]
      ]]
    ];
    const grid=el("div","guideGrid");
    for(const [groupTitle,items] of groups){
      const card=el("section","guideGroup");
      add(card,el("h4",null,groupTitle));
      for(const [label,key] of items){
        const item=el("div","guideItem");
        const sensor=match(key);
        const name=sensor?.attributes?.friendly_name||"Not available";
        add(item,el("span","guideItemTitle",label),
          el("small","guideFriendly",name));
        const controls=el("div","guideCopyRow");
        const field=el("input","guideCopyInput");
        field.type="text";
        field.readOnly=true;
        field.value=sensor?.entity_id||"Not available — check integration";
        field.title=sensor?.entity_id||"Sensor has not been loaded";
        field.setAttribute("aria-label",label+" Home Assistant entity ID");
        if(sensor)field.addEventListener("click",()=>field.select());
        const copy=el("button","guideCopyButton","Copy");
        copy.type="button";copy.disabled=!sensor;
        copy.setAttribute("aria-label","Copy "+label+" entity ID");
        if(sensor)copy.addEventListener("click",()=>this._copyEntityId(sensor.entity_id,copy));
        add(controls,field,copy);add(item,controls);card.append(item);
      }
      grid.append(card);
    }
    add(guide,grid);
    add(guide,el("p","historyFoot",
      "Grid import/export direction is provisional until verified with your utility meter. "+
      "Under grid power measurement choose Standard + signed W, OR Two sensors + import/export W. "+
      "Battery charge and discharge use separate cumulative kWh sensors. "+
      "Missing sensors may require enabling entities or waiting for Recorder statistics."));
    return guide;
  }
  _forecastState(){
    if(!this._hass?.states)return null;
    const states=Object.values(this._hass.states);
    const matches=states.filter(st=>st.attributes?.saj_tou_role==="editable_forecast");
    return matches.find(st=>st.attributes.saj_tou_entry_id===this._selected)
      ||matches[0]||null;
  }
  _forecastSettings(){
    return this._forecastState()?.attributes?.settings||{
      groups:[{count:9,watts:440,azimuth:29,tilt:25},
              {count:15,watts:440,azimuth:27,tilt:25},
              {count:6,watts:440,azimuth:299,tilt:25}],
      efficiency:87,ac_limit_kw:10,configured:false};
  }
  _forecastPage(){
    const section=el("section");
    const header=el("div","forecastHeader");
    add(header,el("h2",null,"Solar forecast"),
      el("span","muted","Open-Meteo · Read-only weather estimate"));
    add(section,header);
    const state=this._forecastState();
    const data=state?.attributes||{};
    if(!state)add(section,el("p","forecastNotice",
      "Forecast settings are not yet available. Update the control integration and restart Home Assistant."));
    const stats=el("div","forecastStats");
    for(const [title,value] of [
      ["Today",data.today],["Remaining today",data.remaining_today],
      ["Tomorrow",data.tomorrow],["Next seven days",data.week]
    ]){
      const item=el("div","forecastStat");
      add(item,el("span","muted",title),el("b",null,
        typeof value==="number"?fmtEnergy(value):"—"));
      stats.append(item);
    }
    add(section,stats);
    if(data.updated)add(section,el("p","muted",
      "Forecast updated: "+formatLocalTime(data.updated)));
    add(section,el("p","muted",
      "PV-side energy forecast. The AC inverter limit does not necessarily cap total PV production while charging the battery."));
    const learning=data.learning||{};
    const historical=learning.historical||{};
    const issued=learning.issued_forecast_accuracy||{};
    const card=el("section","forecastSettings forecastLearning");
    add(card,el("h3",null,"Forecast learning & accuracy"));
    const summary=el("div","learningSummary");
    for(const [label,value,help] of [
      ["Live learning",(learning.clear_sky_hours??0)+" h",
       "Clear-sky recorded hours"],
      ["Historical model",historical.approved?"Validated":
       (historical.eligible_hours??0)+" h available",
       historical.status||"History not analysed"],
      ["Forward accuracy",typeof issued.mae_kwh==="number"?
       issued.mae_kwh.toFixed(2)+" kWh MAE":"Pending",
       (issued.days_scored||0)+" saved predictions scored"+
       (issued.days_scored>=10?" · "+issued.trend:"")]
    ]){
      const box=el("div","learningStat");
      add(box,el("span","muted",label),el("strong",null,value),
        el("small","muted",help));
      summary.append(box);
    }
    add(card,summary);
    const controls=el("div","learningControls");
    const lookback=el("select","learningSelect");
    for(const [number,label] of [[30,"30 days"],[90,"90 days"],
                                  [180,"6 months"],[365,"12 months"]]){
      const opt=el("option",null,label);
      opt.value=String(number);
      opt.selected=number===this._forecastScanDays;
      lookback.append(opt);
    }
    lookback.setAttribute("aria-label","Past data to analyse");
    lookback.addEventListener("change",()=>this._forecastScanDays=Number(lookback.value));
    const run=el("button","secondaryAction",
      this._forecastScanBusy||learning.historical_scanning?
      "Analysing…":"Analyse past readings");
    run.type="button";
    run.disabled=!state||this._forecastScanBusy||learning.historical_scanning;
    run.addEventListener("click",()=>this._scanForecastHistory());
    add(controls,lookback,run);
    add(card,controls);
    if(this._forecastScanMessage)add(card,el("p","muted",this._forecastScanMessage));
    if(learning.historical_error)add(card,el("p","forecastNotice",
      "History scan: "+learning.historical_error));
    const details=el("details","learningDetails");
    add(details,el("summary",null,"Calibration checks & limitations"));
    if(typeof historical.base_mae_kwh==="number"&&
       typeof historical.corrected_mae_kwh==="number"){
      add(details,el("p",null,
        "Historical holdout · Baseline "+historical.base_mae_kwh.toFixed(2)+
        " kWh MAE · Adjusted "+historical.corrected_mae_kwh.toFixed(2)+
        " kWh MAE · "+(historical.approved?"Validated":"Not applied")));
    }
    add(details,el("p","muted",
      "Recorder solar statistics: "+(historical.power_stat_hours??0)+
      " hours · Battery SOC statistics: "+(historical.soc_stat_hours??0)+
      " hours · Qualifying clear-sky samples: "+
      (historical.eligible_hours??0)+" hours."));
    if(typeof issued.previous_five_mae_kwh==="number"&&
       typeof issued.recent_five_mae_kwh==="number")
      add(details,el("p","muted",
        "Issued-forecast error · Previous 5 days: "+
        issued.previous_five_mae_kwh.toFixed(2)+" kWh MAE · "+
        "Latest 5 days: "+issued.recent_five_mae_kwh.toFixed(2)+
        " kWh MAE · "+issued.trend+
        ". This is indicative, not proof of long-term improvement."));
    if(historical.seasonal_hours)
      add(details,el("p","muted","Seasons: "+
        Object.entries(historical.seasonal_hours).map(([k,v])=>k+" "+v+" h").join(" · ")));
    if(learning.historical_last_scan)
      add(details,el("p","muted",
        "Last scan "+formatLocalTime(learning.historical_last_scan)+
        " · "+(learning.historical_source||"Recorder")));
    add(details,el("p","historyFoot",
      "Historical weather reanalysis is a hindsight calibration, not an archived forecast. "+
      "An earlier-to-later holdout must show lower error before corrections are enabled. "+
      "Forward MAE uses actual forecasts stored before the target day and compares matching "+
      "07:00–18:59 solar output. Missing Recorder hours cannot be reconstructed. "+
      "No inverter writes, no automatic TOU changes."));
    add(card,details);
    add(section,card);
    const daily=Array.isArray(data.daily)?data.daily:[];
    const heading=el("h3",null,"Next seven days");add(section,heading);
    const days=el("div","forecastDays");
    const dayTooltip=el("div","forecastBarTooltip");
    dayTooltip.textContent="Hover, tap or focus a day for its predicted solar energy.";
    const max=Math.max(1,...daily.map(d=>Number(d.kwh)||0));
    for(const day of daily){
      const row=el("div","forecastDay");
      const date=new Date(day.date+"T12:00:00");
      const name=Number.isNaN(date.getTime())?day.date:
        date.toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"});
      const track=el("div","forecastTrack");
      const fill=el("div","forecastFill");
      fill.style.width=Math.max(0,Math.min(100,(Number(day.kwh)||0)/max*100))+"%";
      track.append(fill);
      add(row,el("span",null,name),track,
        el("strong",null,fmtEnergy(Number(day.kwh)||0)));
      this._bindForecastBar(row,dayTooltip,
        "Forecast for "+name+": "+(Number(day.kwh)||0).toFixed(2)+" kWh"+
        " · estimate, not measured production");
      days.append(row);
    }
    if(!daily.length)add(days,el("p","muted","Forecast pending weather service response."));
    add(section,days,dayTooltip);
    const hourly=Array.isArray(data.hourly_today)?data.hourly_today:[];
    add(section,el("h3",null,"Actual vs projected · Today"));
    add(section,this._actualProjectedChart(hourly));
    const hoursDetail=el("details","forecastHourly");
    add(hoursDetail,el("summary","costDetailsSummary",
      "Hourly forecast · "+hourly.length+" time slots (hover for readings)"));
    if(hourly.length){
      const plot=el("div","forecastDays");
      const hourlyTooltip=el("div","forecastBarTooltip");
      hourlyTooltip.textContent="Hover, tap or focus a period to inspect forecast and cloud cover.";
      const peak=Math.max(1,...hourly.map(h=>Number(h.kwh)||0));
      for(const h of hourly){
        const row=el("div","forecastDay");
        const track=el("div","forecastTrack");
        const fill=el("div","forecastFill");
        fill.style.width=Math.max(0,Math.min(100,(Number(h.kwh)||0)/peak*100))+"%";
        track.append(fill);
        add(row,el("span",null,h.hour),track,
          el("span",null,(Number(h.kwh)||0).toFixed(2)+" kWh"));
        this._bindForecastBar(row,hourlyTooltip,
          "Forecast for "+h.hour+"–next hour: "+
          (Number(h.kwh)||0).toFixed(2)+" kWh"+
          (typeof h.cloud==="number"?" · Cloud cover "+h.cloud+"%":""));
        plot.append(row);
      }
      add(hoursDetail,plot,hourlyTooltip);
    }else add(hoursDetail,el("p","muted","Hourly weather forecast is unavailable."));
    add(section,hoursDetail);
    const settings=this._forecastSettings();
    if(this._forecastEditorOpen===null)this._forecastEditorOpen=!settings.configured;
    if(!this._forecastForm)this._forecastForm={
      groups:settings.groups.map(g=>({...g})),
      efficiency:settings.efficiency,ac_limit_kw:settings.ac_limit_kw
    };
    const settingsShell=el("details","forecastSettingsShell");
    settingsShell.open=Boolean(this._forecastEditorOpen);
    settingsShell.addEventListener("toggle",()=>{
      this._forecastEditorOpen=settingsShell.open;
    });
    add(settingsShell,el("summary","costDetailsSummary",
      "Solar system settings · Panel groups, orientations & efficiency"));
    const wrapper=el("section","forecastSettings");
    add(wrapper,el("h3",null,"Your solar system settings"));
    if(!settings.configured)add(wrapper,el("p","forecastNotice",
      "These are example defaults from the original 30-panel SAJ installation. Please review and change them to match YOUR roof, panel layout, inverter and efficiency before relying on this forecast."));
    const form=this._forecastForm;
    const groups=el("div");
    const field=(label,value,step,min,max,onChange)=>{
      const holder=el("label");
      holder.append(el("span",null,label));
      const input=el("input");
      input.type="number";input.step=String(step);
      input.min=String(min);input.max=String(max);input.value=String(value);
      input.addEventListener("change",()=>{
        const n=Number(input.value);
        if(Number.isFinite(n))onChange(n);
      });
      holder.append(input);
      return holder;
    };
    const rebuild=()=>{
      this._forecastForm=form;this.render();
    };
    form.groups.forEach((g,i)=>{
      const row=el("div","forecastSettingGrid");
      add(row,
        field("Panels",g.count,1,1,100,v=>g.count=v),
        field("Watts / panel",g.watts,1,1,800,v=>g.watts=v),
        field("Azimuth ° from north",g.azimuth,1,0,360,v=>g.azimuth=v),
        field("Tilt °",g.tilt,1,0,90,v=>g.tilt=v));
      const remove=el("button",null,"Remove group "+(i+1));
      remove.type="button";remove.disabled=form.groups.length<=1;
      remove.addEventListener("click",()=>{form.groups.splice(i,1);rebuild();});
      const item=el("div","pane");
      add(item,el("strong",null,"Panel group "+(i+1)),row,remove);
      groups.append(item);
    });
    add(wrapper,groups);
    const addGroup=el("button",null,"+ Add panel group");
    addGroup.type="button";addGroup.disabled=form.groups.length>=8;
    addGroup.addEventListener("click",()=>{
      form.groups.push({count:1,watts:440,azimuth:0,tilt:25});rebuild();
    });
    add(wrapper,addGroup);
    const totals=el("div","forecastSettingGrid");
    add(totals,
      field("System efficiency (%)",form.efficiency,1,1,100,v=>form.efficiency=v),
      field("Inverter AC limit (kW)",form.ac_limit_kw,0.1,0.5,100,v=>form.ac_limit_kw=v));
    add(wrapper,totals);
    const dc=form.groups.reduce((sum,g)=>sum+g.count*g.watts,0);
    add(wrapper,el("p","muted",
      "Total DC array: "+form.groups.reduce((sum,g)=>sum+g.count,0)+
      " panels · "+(dc/1000).toFixed(2)+" kWp. Azimuth: 0° north, 90° east, 180° south, 270° west."));
    const save=el("button","primaryAction",
      this._forecastSaving?"Saving & recalculating…":"Save settings & recalculate");
    save.disabled=this._forecastSaving||!state;
    save.addEventListener("click",()=>this._saveForecastSettings());
    add(wrapper,save);
    if(this._forecastMessage)add(wrapper,el("p",
      this._forecastError?"bad":"okay",this._forecastMessage));
    add(wrapper,el("p","historyFoot",
      "Only the forecast model is changed. No inverter operating mode, battery setting or schedule is modified."));
    add(settingsShell,wrapper);
    add(section,settingsShell);
    return section;
  }
  async _scanForecastHistory(){
    if(this._forecastScanBusy||!this._hass)return;
    this._forecastScanBusy=true;
    this._forecastScanMessage="Scanning available HA statistics and historical weather…";
    this.render();
    try{
      const data={days:this._forecastScanDays};
      if(this._selected&&!this._selected.startsWith("sensor."))data.entry_id=this._selected;
      const response=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"scan_forecast_history",service_data:data,return_response:true
      });
      const result=response?.response?.result||response?.result||response?.response||{};
      this._forecastScanMessage=(result.status||"Scan complete")+
        (typeof result.eligible_hours==="number"?
        " · "+result.eligible_hours+" qualifying hours":"")+
        (result.error?" · "+result.error:"");
    }catch(error){
      this._forecastScanMessage="Unable to analyse: "+(error?.message||String(error));
    }finally{
      this._forecastScanBusy=false;
      this.render();
    }
  }
  async _saveForecastSettings(){
    const f=this._forecastForm;
    const count=f.groups.reduce((sum,g)=>sum+g.count,0);
    if(!f.groups.length||f.groups.length>8||count>800||
       f.groups.some(g=>!Number.isInteger(g.count)||g.count<1||g.count>100||
         !Number.isFinite(g.watts)||g.watts<1||g.watts>800||
         !Number.isFinite(g.azimuth)||g.azimuth<0||g.azimuth>360||
         !Number.isFinite(g.tilt)||g.tilt<0||g.tilt>90)||
       !Number.isFinite(f.efficiency)||f.efficiency<1||f.efficiency>100||
       !Number.isFinite(f.ac_limit_kw)||f.ac_limit_kw<0.5||f.ac_limit_kw>100){
      this._forecastMessage="Check group counts, wattage, azimuth, tilt, efficiency and AC limit.";
      this._forecastError=true;this.render();return;
    }
    this._forecastSaving=true;this._forecastMessage="";this.render();
    try{
      const data={
        groups_json:JSON.stringify(f.groups),efficiency:f.efficiency,
        ac_limit_kw:f.ac_limit_kw
      };
      if(this._selected && !this._selected.startsWith("sensor."))data.entry_id=this._selected;
      const response=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"save_forecast_settings",service_data:data,return_response:true
      });
      this._forecastMessage=response?.response?.forecast_available===false?
        "Settings saved. Weather service unavailable; retry with refresh later.":
        "Settings saved. Forecast recalculated from your panel layout.";
      this._forecastError=false;this._forecastForm=null;
      this._forecastEditorOpen=false;
    }catch(err){
      this._forecastError=true;
      this._forecastMessage="Forecast settings not saved: "+(err?.message||String(err));
    }finally{this._forecastSaving=false;this.render();}
  }
  _bindForecastBar(row,tooltip,message){
    // Real touch/mouse/keyboard inspection for forecast bars.
    row.tabIndex=0;
    row.setAttribute("role","img");
    row.setAttribute("aria-label",message);
    row.title=message;
    const reveal=()=>{tooltip.textContent=message;};
    row.addEventListener("pointerenter",reveal);
    row.addEventListener("pointerdown",reveal);
    row.addEventListener("focus",reveal);
    row.addEventListener("click",reveal);
  }
  async _loadForecastHistory(force=false){
    if(this._forecastHistoryPending||!this._hass)return;
    const now=new Date();
    const start=new Date(now);
    start.setHours(0,0,0,0);
    const date=start.toLocaleDateString("en-CA");
    if(!force&&this._forecastHistoryDate===date&&
       Date.now()-this._forecastHistoryFetchedAt<5*60000)return;
    this._forecastHistoryPending=true;
    this._forecastHistoryError="";
    try{
      const query="?filter_entity_id="+encodeURIComponent(SAFE_ENERGY_IDS.solar)+
        "&end_time="+encodeURIComponent(now.toISOString())+"&minimal_response";
      const response=await this._hass.callApi("GET",
        "history/period/"+encodeURIComponent(start.toISOString())+query);
      if(!Array.isArray(response))throw Error("Unexpected Recorder data");
      const samples=[];
      for(const series of response){
        if(!Array.isArray(series)||!series.length)continue;
        const id=series.find(v=>v.entity_id)?.entity_id;
        if(id!==SAFE_ENERGY_IDS.solar)continue;
        for(const item of series){
          const time=Date.parse(item.last_changed||item.last_updated||"");
          const state=String(item.state);
          if(["unknown","unavailable",""].includes(state))continue;
          const watts=Number(state);
          if(Number.isFinite(time)&&time>=start.getTime()&&time<=now.getTime()&&
             Number.isFinite(watts)&&watts>=0)samples.push({t:time,y:watts});
        }
      }
      samples.sort((a,b)=>a.t-b.t);
      this._forecastHistoryData=samples;
      this._forecastHistoryDate=date;
      this._forecastHistoryFetchedAt=Date.now();
    }catch(error){
      this._forecastHistoryError="Could not read recorded solar power: "+
        (error?.message||String(error));
      this._forecastHistoryData=[];
      this._forecastHistoryDate=date;
      this._forecastHistoryFetchedAt=Date.now();
    }finally{
      this._forecastHistoryPending=false;
      if(this._page==="forecast"&&!this._forecastSaving)this.render();
    }
  }
  _actualProjectedChart(hourly){
    const panel=el("section","forecastHistory actualForecast");
    const heading=el("div","historyHead");
    const description=el("div");
    add(description,el("h4",null,"Today · Cumulative solar energy (kWh)"),
      el("div","muted","Forecast vs recorded production · hover, tap or use ← / →"));
    const refresh=el("button","guideCopyButton","Refresh actual readings");
    refresh.type="button";
    refresh.disabled=this._forecastHistoryPending;
    refresh.addEventListener("click",()=>{
      this._forecastHistoryFetchedAt=0;
      this._loadForecastHistory(true);
    });
    add(heading,description,refresh);
    add(panel,heading);
    if(!hourly.length){
      add(panel,el("p","muted","Hourly weather forecast not available."));
      return panel;
    }
    const now=new Date();
    const midnight=new Date(now);
    midnight.setHours(0,0,0,0);
    const midnightMs=midnight.getTime();
    if(this._forecastHistoryDate!==midnight.toLocaleDateString("en-CA")||
       (!this._forecastHistoryPending &&
        (!this._forecastHistoryData||Date.now()-this._forecastHistoryFetchedAt>5*60000)))
      this._loadForecastHistory();
    const records=Array.isArray(this._forecastHistoryData)?this._forecastHistoryData:[];
    const projected=[{hour:0,kwh:0}];
    let sum=0;
    for(const h of [...hourly].sort((a,b)=>a.hour.localeCompare(b.hour))){
      const startHour=Number(String(h.hour).slice(0,2));
      if(!Number.isInteger(startHour)||startHour<0||startHour>=24)continue;
      sum+=Math.max(0,Number(h.kwh)||0);
      projected.push({hour:startHour+1,kwh:sum});
    }
    projected.sort((a,b)=>a.hour-b.hour);
    const actual=[];
    let total=0,previous=null,missingSeconds=0;
    for(const item of records){
      if(previous){
        const dt=item.t-previous.t;
        if(dt>0&&dt<=30*60000){
          total+=(Math.max(0,item.y)+Math.max(0,previous.y))*dt/7200000000;
        }else if(dt>30*60000)missingSeconds+=dt/1000;
      }
      actual.push({t:item.t,hour:(item.t-midnightMs)/3600000,kwh:total});
      previous=item;
    }
    const peak=Math.max(1,...projected.map(v=>v.kwh),...actual.map(v=>v.kwh));
    const ns="http://www.w3.org/2000/svg";
    const svg=document.createElementNS(ns,"svg");
    svg.setAttribute("viewBox","0 0 920 300");
    svg.setAttribute("class","historySvg forecastSvg");
    svg.setAttribute("role","img");
    svg.setAttribute("tabindex","0");
    svg.setAttribute("aria-label",
      "Cumulative forecast versus recorded solar energy. Move pointer or use left and right arrow keys in five-minute steps.");
    const shape=(tag,attrs,textValue)=>{
      const node=document.createElementNS(ns,tag);
      for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));
      if(textValue!==undefined)node.textContent=String(textValue);
      svg.append(node);
      return node;
    };
    const L=48,R=896,T=20,B=252;
    const x=h=>L+Math.max(0,Math.min(24,h))/24*(R-L);
    const y=k=>B-Math.max(0,Math.min(1,k/peak))*(B-T);
    for(let i=0;i<=4;i++){
      const level=peak*i/4,yy=y(level);
      shape("line",{x1:L,y1:yy,x2:R,y2:yy,
        stroke:"currentColor","stroke-opacity":i===0?".3":".12"});
      shape("text",{x:L-8,y:yy+4,fill:"currentColor",
        "fill-opacity":".75","font-size":12,"text-anchor":"end"},level.toFixed(0));
    }
    shape("text",{x:12,y:13,fill:"currentColor","font-size":12},"kWh");
    for(let h=0;h<=24;h+=4){
      const xx=x(h);
      shape("text",{x:xx,y:278,fill:"currentColor","font-size":12,
        "text-anchor":h===0?"start":h===24?"end":"middle"},
        String(h).padStart(2,"0")+":00");
    }
    const actualChunks=[];
    let chunk=[],last=null;
    for(const sample of actual){
      if(last!==null&&sample.t-last>30*60000&&chunk.length){
        actualChunks.push(chunk);chunk=[];
      }
      chunk.push(sample);last=sample.t;
    }
    if(chunk.length)actualChunks.push(chunk);
    const paths=[
      {series:[projected],color:"#eab54c"},
      {series:actualChunks,color:"#55a4ed"}
    ];
    for(const pathGroup of paths){
      for(const points of pathGroup.series){
        if(points.length<2)continue;
        const d=points.map((pt,i)=>(i?"L":"M")+x(pt.hour).toFixed(1)+","+
          y(pt.kwh).toFixed(1)).join(" ");
        shape("path",{d,stroke:pathGroup.color,"stroke-width":2.7,fill:"none",
          "stroke-linecap":"round","stroke-linejoin":"round"});
      }
    }
    const cursor=shape("line",{x1:L,y1:T,x2:L,y2:B,
      stroke:"currentColor","stroke-width":1.2,"stroke-dasharray":"4 4",
      "stroke-opacity":".65",visibility:"hidden","pointer-events":"none"});
    const actualDot=shape("circle",{cx:L,cy:B,r:4,fill:"#55a4ed",
      stroke:"var(--ha-card-background,#202124)","stroke-width":2,
      visibility:"hidden","pointer-events":"none"});
    const expectedDot=shape("circle",{cx:L,cy:B,r:4,fill:"#eab54c",
      stroke:"var(--ha-card-background,#202124)","stroke-width":2,
      visibility:"hidden","pointer-events":"none"});
    // Transparent hit target allows hovering anywhere in the chart, not
    // just where a colored line happens to be drawn.
    shape("rect",{x:L,y:T,width:R-L,height:B-T,fill:"transparent",
      "pointer-events":"all"});
    const tooltip=el("div","historyTooltip forecastTooltip");
    tooltip.setAttribute("role","status");
    tooltip.textContent="Hover or tap the graph for values at a chosen time (5-minute cursor).";
    const findRecorded=(time)=>{
      if(!actual.length)return null;
      let lo=0,hi=actual.length;
      while(lo<hi){
        const mid=(lo+hi)>>1;
        if(actual[mid].t<time)lo=mid+1;else hi=mid;
      }
      const candidates=[actual[lo-1],actual[lo]].filter(Boolean);
      const nearest=candidates.reduce((a,b)=>!a||
        Math.abs(b.t-time)<Math.abs(a.t-time)?b:a,null);
      return nearest&&Math.abs(nearest.t-time)<=10*60000?nearest:null;
    };
    const fmtTime=t=>new Date(t).toLocaleTimeString(undefined,
      {hour:"2-digit",minute:"2-digit"});
    const showAt=(fraction)=>{
      const hour=Math.max(0,Math.min(24,
        Math.round(fraction*24*12)/12));
      const t=midnightMs+hour*3600000;
      const prior=projected.filter(pt=>pt.hour<=hour).at(-1);
      const measured=findRecorded(t);
      const cursorX=x(hour);
      cursor.setAttribute("x1",cursorX);
      cursor.setAttribute("x2",cursorX);
      cursor.setAttribute("visibility","visible");
      expectedDot.setAttribute("visibility",prior?"visible":"hidden");
      if(prior){expectedDot.setAttribute("cx",x(prior.hour));
        expectedDot.setAttribute("cy",y(prior.kwh));}
      actualDot.setAttribute("visibility",measured?"visible":"hidden");
      if(measured){actualDot.setAttribute("cx",x(measured.hour));
        actualDot.setAttribute("cy",y(measured.kwh));}
      tooltip.replaceChildren();
      add(tooltip,el("strong",null,fmtTime(t)));
      const expected=el("span","historyValue",
        "● Forecast through "+String(prior?.hour??0).padStart(2,"0")+
        ":00 · "+(prior?prior.kwh.toFixed(2)+" kWh":"—"));
      expected.style.color="#eab54c";
      const reported=el("span","historyValue",
        "● Recorded "+(measured?
          measured.kwh.toFixed(2)+" kWh at "+fmtTime(measured.t):
          "— no nearby measurement"));
      reported.style.color="#55a4ed";
      add(tooltip,expected,reported);
    };
    let keyboardFraction=0;
    svg.addEventListener("pointermove",event=>{
      const bounds=svg.getBoundingClientRect();
      if(!bounds.width)return;
      const position=(event.clientX-bounds.left)/bounds.width*920;
      if(position<L||position>R)return;
      keyboardFraction=(position-L)/(R-L);
      showAt(keyboardFraction);
    });
    svg.addEventListener("pointerdown",event=>{
      const bounds=svg.getBoundingClientRect();
      if(!bounds.width)return;
      const position=(event.clientX-bounds.left)/bounds.width*920;
      keyboardFraction=Math.max(0,Math.min(1,(position-L)/(R-L)));
      showAt(keyboardFraction);
    });
    svg.addEventListener("pointerleave",()=>{
      cursor.setAttribute("visibility","hidden");
      actualDot.setAttribute("visibility","hidden");
      expectedDot.setAttribute("visibility","hidden");
    });
    svg.addEventListener("keydown",event=>{
      if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;
      event.preventDefault();
      keyboardFraction=Math.max(0,Math.min(1,keyboardFraction+
        (event.key==="ArrowRight"?1:-1)/288));
      showAt(keyboardFraction);
    });
    add(panel,svg,tooltip);
    add(panel,el("p","historyFoot",
      "Yellow: forecast from hourly irradiance. Blue: solar energy integrated from available Recorder power samples"+
      (records.length?" since "+fmtTime(records[0].t):" (waiting for samples)")+
      ". This blue total may be LOW if recordings started late or contain gaps"+
      (missingSeconds>60?" ("+(missingSeconds/3600).toFixed(1)+" hours of gaps)":"")+
      ". Gaps in actual readings are shown as breaks. No missing energy is fabricated."));
    if(this._forecastHistoryError)
      add(panel,el("p","muted",this._forecastHistoryError));
    return panel;
  }
  _historyChart(){
    const panel=el("section","forecastHistory liveHistory");
    const heading=el("div","historyHead");
    const title=el("div");
    add(title,el("h3",null,"Historic Data"),
      el("div","muted","Recorded power · kW · signed battery and grid flow"));
    const select=el("select");
    for(const hours of [6,12,24,48,168]){
      const option=el("option",null,hours===168?"7 days":hours+" hours");
      option.value=String(hours);
      option.selected=hours===this._historyHours;
      select.append(option);
    }
    select.setAttribute("aria-label","Historic Data time range");
    select.addEventListener("change",()=>{
      this._historyHours=Number(select.value);
      this._historyData=null;
      this._historySignature="";
      const old=this.shadowRoot.querySelector(".liveHistory");
      if(old)old.replaceWith(this._historyChart());
    });
    add(heading,title,select);add(panel,heading);
    const labels={solar:"Solar production",home:"House usage",battery:"Battery ±",grid:"Grid ±"};
    const colors={solar:"#eab54c",home:"#51a7ee",battery:"#46c79e",grid:"#c08df0"};
    const legend=el("div","historyLegend");
    for(const [key,label] of Object.entries(labels)){
      const holder=el("label","historyToggle");
      const checkbox=el("input");
      checkbox.type="checkbox";checkbox.checked=this._historyVisible[key]!==false;
      checkbox.addEventListener("change",()=>{
        this._historyVisible[key]=checkbox.checked;
        const old=this.shadowRoot.querySelector(".liveHistory");
        if(old)old.replaceWith(this._historyChart());
      });
      const dot=el("span","historyDot","●");
      dot.style.color=colors[key];
      add(holder,checkbox,dot,el("span",null,label));legend.append(holder);
    }
    add(panel,legend);
    const history=this._historyData;
    if(!history){
      add(panel,el("p","muted",this._historyError||
        "Loading Home Assistant recorded history…"));
      if(!this._historyPending)this._loadHistory();
      return panel;
    }
    const activeKeys=Object.keys(labels).filter(k=>this._historyVisible[k]!==false);
    const series={
      solar:history.solar||[],
      home:history.home||[],
      battery:history.battery||[],
      gridImport:history.gridImport||[],
      gridExport:history.gridExport||[]
    };
    const displayed=activeKeys.flatMap(k=>k==="grid"?
      [...series.gridImport,...series.gridExport.map(p=>({t:p.t,y:-p.y}))]:
      series[k]);
    if(!displayed.length){
      add(panel,el("p","muted",
        "No recorded measurements for the selected period. Check Home Assistant Recorder or select a longer interval."));
      return panel;
    }
    const now=Date.now(),start=now-this._historyHours*3600000;
    const values=displayed.filter(p=>p.t>=start&&p.t<=now).map(p=>p.y/1000);
    const maxRaw=Math.max(0,...values),minRaw=Math.min(0,...values);
    // Rounded human-readable major intervals: 0.5, 1, 2, 5, 10, ... kW
    const niceStep=(v)=>{
      if(v<=0)return 1;
      const mag=Math.pow(10,Math.floor(Math.log10(v)));
      return [1,2,2.5,5,10].map(n=>n*mag).find(n=>n>=v)||10*mag;
    };
    const step=niceStep((maxRaw-minRaw)/5||0.2);
    let high=Math.max(step,Math.ceil(maxRaw/step)*step);
    let low=Math.min(0,Math.floor(minRaw/step)*step);
    if(high-low>step*9){const wider=niceStep((maxRaw-minRaw)/6);high=Math.max(wider,Math.ceil(maxRaw/wider)*wider);low=Math.min(0,Math.floor(minRaw/wider)*wider);}
    const ns="http://www.w3.org/2000/svg";
    const svg=document.createElementNS(ns,"svg");
    svg.setAttribute("viewBox","0 0 960 360");
    svg.setAttribute("class","historySvg");
    svg.setAttribute("role","img");
    svg.setAttribute("aria-label","Recorded power history in kilowatts, showing battery charging below zero and grid exports below zero");
    const make=(tag,attrs,content)=>{
      const item=document.createElementNS(ns,tag);
      Object.entries(attrs).forEach(([k,v])=>item.setAttribute(k,String(v)));
      if(content!==undefined)item.textContent=content;
      svg.append(item);return item;
    };
    const L=63,R=938,T=22,B=306;
    const x=t=>L+Math.max(0,Math.min(1,(t-start)/(now-start)))*(R-L);
    const y=w=>B-(w/1000-low)/(high-low)*(B-T);
    const gridStep=niceStep((high-low)/6);
    const digits=gridStep<1?1:0;
    for(let v=Math.ceil(low/gridStep)*gridStep;v<=high+gridStep/100;v+=gridStep){
      const py=y(v*1000);
      make("line",{x1:L,y1:py,x2:R,y2:py,stroke:"currentColor",
        "stroke-opacity":Math.abs(v)<gridStep/100?".53":".11",
        "stroke-width":Math.abs(v)<gridStep/100?1.6:1});
      make("text",{x:L-11,y:py+4,fill:"currentColor","fill-opacity":".8",
        "text-anchor":"end","font-size":13},Math.abs(v)<gridStep/100?"0":v.toFixed(digits));
    }
    for(let i=0;i<=6;i++){
      const dt=new Date(start+(now-start)*i/6);
      const xx=x(dt.getTime());
      make("line",{x1:xx,y1:T,x2:xx,y2:B,stroke:"currentColor","stroke-opacity":".045"});
      make("text",{x:xx,y:336,fill:"currentColor","fill-opacity":".72",
        "text-anchor":i===0?"start":i===6?"end":"middle","font-size":12},
        dt.toLocaleString(undefined,this._historyHours<=24?
          {hour:"2-digit",minute:"2-digit"}:
          {month:"short",day:"numeric",hour:"2-digit"}));
    }
    make("text",{x:L,y:13,fill:"currentColor","fill-opacity":".7","font-size":12},"kW");
    const plot=(points,color,negative=false)=>{
      const valid=points.filter(p=>p.t>=start&&p.t<=now).sort((a,b)=>a.t-b.t);
      if(!valid.length)return;
      // Time-gap boundaries prevent long lines across missing recorder data.
      const maxGap=this._historyHours>=168?4*3600000:45*60000;
      let chunks=[],chunk=[],last=null;
      for(const p of valid){
        if(last!==null&&p.t-last>maxGap&&chunk.length){chunks.push(chunk);chunk=[];}
        chunk.push(p);last=p.t;
      }
      if(chunk.length)chunks.push(chunk);
      for(const points of chunks){
        // Preserve minima and maxima within time buckets, rather than
        // simple stride sampling that can erase rapid power spikes.
        const target=450;
        const compact=points.length<=target?points:(()=>{
          const result=[],size=Math.ceil(points.length/(target/2));
          for(let i=0;i<points.length;i+=size){
            const bucket=points.slice(i,i+size);
            let lo=bucket[0],hi=bucket[0];
            for(const p of bucket){if(p.y<lo.y)lo=p;if(p.y>hi.y)hi=p;}
            result.push(...(lo.t===hi.t?[lo]:lo.t<hi.t?[lo,hi]:[hi,lo]));
          }
          return result;
        })();
        const d=compact.map((p,i)=>(i?"L":"M")+x(p.t).toFixed(1)+","+
          y((negative?-1:1)*p.y).toFixed(1)).join(" ");
        make("path",{d,fill:"none",stroke:color,"stroke-width":2.2,
          "stroke-opacity":".96","stroke-linejoin":"round","stroke-linecap":"round"});
      }
    };
    if(activeKeys.includes("solar"))plot(series.solar,colors.solar);
    if(activeKeys.includes("home"))plot(series.home,colors.home);
    if(activeKeys.includes("battery"))plot(series.battery,colors.battery);
    if(activeKeys.includes("grid")){
      plot(series.gridImport,colors.grid);
      plot(series.gridExport,colors.grid,true);
    }
    // Mouse/touch/keyboard inspection: snaps to a time slot and reports the
    // actual timestamp and reading nearest that slot, never an invented sample.
    const intervalMinutes=this._historyHours<=24?5:this._historyHours<=48?10:30;
    const intervalMs=intervalMinutes*60000;
    const cursor=make("line",{x1:L,y1:T,x2:L,y2:B,stroke:"currentColor",
      "stroke-opacity":".7","stroke-width":1.3,"stroke-dasharray":"4 4",
      visibility:"hidden","pointer-events":"none"});
    const markers={};
    for(const [key,color] of Object.entries(colors)){
      markers[key]=make("circle",{cx:L,cy:T,r:4.8,fill:color,
        stroke:"var(--ha-card-background,#202124)","stroke-width":2,
        visibility:"hidden","pointer-events":"none"});
    }
    const tooltip=el("div","historyTooltip");
    tooltip.setAttribute("role","status");
    tooltip.setAttribute("aria-live","off");
    const intro=el("span","historyEmpty",
      "Hover, tap or use ← / → on the graph to inspect recorded readings ("+
      intervalMinutes+"-minute steps).");
    tooltip.append(intro);
    const nearest=(points,epoch)=>{
      if(!points?.length)return null;
      // Find the closest actual recorder sample using binary search.
      let lo=0,hi=points.length;
      while(lo<hi){
        const mid=(lo+hi)>>1;
        if(points[mid].t<epoch)lo=mid+1;else hi=mid;
      }
      const candidates=[points[lo-1],points[lo]].filter(Boolean);
      const best=candidates.reduce((a,b)=>!a||
        Math.abs(b.t-epoch)<Math.abs(a.t-epoch)?b:a,null);
      return best&&Math.abs(best.t-epoch)<=intervalMs/2?best:null;
    };
    const fmtTimestamp=epoch=>new Date(epoch).toLocaleString(undefined,{
      month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"});
    const showAt=(epoch)=>{
      const snap=Math.max(start,Math.min(now,
        Math.round(epoch/intervalMs)*intervalMs));
      const cursorX=x(snap);
      cursor.setAttribute("x1",cursorX);
      cursor.setAttribute("x2",cursorX);
      cursor.setAttribute("visibility","visible");
      tooltip.replaceChildren(el("strong",null,
        new Date(snap).toLocaleString(undefined,{
          month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})+
        " · nearest actual readings"));
      const readings={
        solar:nearest(series.solar,snap),home:nearest(series.home,snap),
        battery:nearest(series.battery,snap)
      };
      const imp=nearest(series.gridImport,snap);
      const exp=nearest(series.gridExport,snap);
      // Import/export sensor values are complementary only when both present.
      readings.grid=imp&&exp?
        {t:Math.max(imp.t,exp.t),y:imp.y-exp.y}:null;
      for(const [key,label] of Object.entries(labels)){
        const marker=markers[key];
        const value=readings[key];
        const visible=activeKeys.includes(key);
        if(!visible||!value){
          marker.setAttribute("visibility","hidden");
        }else{
          marker.setAttribute("cx",x(value.t));
          marker.setAttribute("cy",y(value.y));
          marker.setAttribute("visibility","visible");
        }
        if(!visible)continue;
        const item=el("span","historyValue");
        item.style.color=colors[key];
        item.textContent=label+": "+(value?
          (value.y/1000).toFixed(2)+" kW":"— no nearby reading");
        if(value){
          item.title="Recorded "+fmtTimestamp(value.t);
        }
        tooltip.append(item);
      }
      const stamped=Object.entries(readings).filter(([k,v])=>
        activeKeys.includes(k)&&v).map(([k,v])=>
        k+": "+new Date(v.t).toLocaleTimeString(undefined,{hour:"2-digit",
          minute:"2-digit",second:"2-digit"}));
      if(stamped.length)add(tooltip,el("small","historyEmpty",
        "Actual sample times — "+stamped.join(" · ")));
    };
    const hide=()=>{
      cursor.setAttribute("visibility","hidden");
      Object.values(markers).forEach(m=>m.setAttribute("visibility","hidden"));
    };
    svg.setAttribute("tabindex","0");
    svg.setAttribute("aria-label",
      "Historic Data graph. Use arrow keys for "+intervalMinutes+
      "-minute intervals, or move pointer to inspect actual recorded power.");
    let keyboardTime=now;
    svg.addEventListener("pointermove",event=>{
      // Pointer location via rendered SVG bounding box, mapped to viewBox.
      const rect=svg.getBoundingClientRect();
      if(!rect.width)return;
      const px=(event.clientX-rect.left)/rect.width*960;
      if(px<L||px>R){hide();return;}
      keyboardTime=start+(px-L)/(R-L)*(now-start);
      showAt(keyboardTime);
    });
    svg.addEventListener("pointerdown",event=>{
      const rect=svg.getBoundingClientRect();
      if(!rect.width)return;
      const px=(event.clientX-rect.left)/rect.width*960;
      if(px<L||px>R)return;
      keyboardTime=start+(px-L)/(R-L)*(now-start);
      showAt(keyboardTime);
    });
    svg.addEventListener("pointerleave",hide);
    svg.addEventListener("keydown",event=>{
      if(event.key!=="ArrowLeft"&&event.key!=="ArrowRight")return;
      event.preventDefault();
      keyboardTime=Math.max(start,Math.min(now,keyboardTime+
        (event.key==="ArrowRight"?intervalMs:-intervalMs)));
      showAt(keyboardTime);
    });
    add(panel,svg,tooltip);
    add(panel,el("p","historyFoot",
      "One scale for every line (kW). Battery above 0 = discharging; below 0 = charging. "+
      "Grid above 0 = importing; below 0 = exporting (direction inferred from SAJ monitor). "+
      "Only actual Home Assistant Recorder measurements are shown; gaps remain gaps."));
    if(this._historyError)add(panel,el("p","bad",this._historyError));
    return panel;
  }
  async _loadHistory(){
    if(this._historyPending||!this._hass)return;
    const ids={
      solar:SAFE_ENERGY_IDS.solar,
      home:SAFE_ENERGY_IDS.home,
      battery:SAFE_ENERGY_IDS.battery,
      gridImport:SAFE_ENERGY_IDS.gridImport,
      gridExport:SAFE_ENERGY_IDS.gridExport
    };
    const idList=Object.values(ids);
    const hours=this._historyHours;
    const start=new Date(Date.now()-hours*3600000);
    const signature=hours+"|"+idList.join("|");
    if(this._historySignature===signature&&this._historyData)return;
    this._historyPending=true;this._historyError="";
    try{
      const query="?filter_entity_id="+encodeURIComponent(idList.join(","))+
        "&end_time="+encodeURIComponent(new Date().toISOString())+
        "&minimal_response";
      const response=await this._hass.callApi("GET",
        "history/period/"+encodeURIComponent(start.toISOString())+query);
      if(!Array.isArray(response))throw Error("Unexpected Home Assistant history format");
      const result={solar:[],home:[],battery:[],gridImport:[],gridExport:[]};
      for(const samples of response){
        if(!Array.isArray(samples)||!samples.length)continue;
        const seriesId=samples.find(sample=>sample.entity_id)?.entity_id;
        const key=Object.keys(ids).find(k=>ids[k]===seriesId);
        if(!key)continue;
        for(const sample of samples){
          const timestamp=Date.parse(sample.last_changed||sample.last_updated||"");
          const raw=String(sample.state);
          if(["unknown","unavailable",""].includes(raw))continue;
          const value=Number(raw);
          if(Number.isFinite(timestamp)&&Number.isFinite(value))
            result[key].push({t:timestamp,y:value});
        }
      }
      for(const points of Object.values(result))points.sort((a,b)=>a.t-b.t);
      // An older request must not replace a newer selected time range.
      if(hours!==this._historyHours)return;
      this._historyData=result;
      this._historySignature=signature;
    }catch(error){
      if(hours!==this._historyHours)return;
      this._historyData={solar:[],home:[],battery:[],gridImport:[],gridExport:[]};
      this._historyError="Recorder history unavailable: "+(error?.message||String(error));
    }finally{
      this._historyPending=false;
      if(hours!==this._historyHours){this._loadHistory();return;}
      if(this._page==="forecast"){
        this.render();
      }else{
        const old=this.shadowRoot?.querySelector(".liveHistory");
        if(old)old.replaceWith(this._historyChart());
      }
    }
  }
  getCardSize() {return 7;}
  getStubConfig() {return {};}
  _energyOverview(){
    const hass=this._hass;
    const panel=el("section","energyOverview");
    const header=el("div","flowTop");
    const energyHeading=el("div","energyHeading");
    const cadence=el("span","energyCadence","↻ Updates ~10 sec (default)");
    cadence.title="SAJ Safe Monitor live polling defaults to 10 seconds and can be changed in integration options. Solar forecasts refresh on a separate schedule.";
    add(energyHeading,el("h3",null,"Live energy"),
      el("div","muted","Solar · Home · Battery · Grid · Forecast"),
      cadence);
    const openForecast=el("button","forecastLink","Forecast details ›");
    openForecast.title="Open detailed solar forecast and system settings inside this dashboard";
    openForecast.addEventListener("click",()=>this._goPage("forecast"));
    add(header,energyHeading,openForecast);
    add(panel,header);
    const keys=["solar","home","battery","soc","stored","gridImport",
      "gridExport","outlook","remaining","tomorrow"];
    const values=Object.fromEntries(keys.map(k=>[k,safeMetric(hass,k)]));
    const editableForecast=this._forecastState();
    const model=editableForecast?.attributes||{};
    const custom=Boolean(model.settings?.configured && model.daily?.length);
    if(custom){
      // Derived actual energy from Safe Monitor's recorded outlook and remaining;
      // avoid mixing old forecast totals with the new user-specific model.
      const actual=values.outlook!==null&&values.remaining!==null?
        Math.max(0,values.outlook-values.remaining):null;
      values.remaining=typeof model.remaining_today==="number"?model.remaining_today:null;
      values.outlook=actual!==null&&values.remaining!==null?
        Math.round((actual+values.remaining)*100)/100:
        typeof model.today==="number"?model.today:null;
      values.tomorrow=typeof model.tomorrow==="number"?model.tomorrow:null;
    }
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
    const forecastHeader=hr.lastElementChild;
    if(forecastHeader){
      forecastHeader.title="Open forecast details";
      forecastHeader.style.cursor="pointer";
      forecastHeader.tabIndex=0;
      forecastHeader.setAttribute("role","button");
      forecastHeader.addEventListener("click",()=>this._goPage("forecast"));
      forecastHeader.addEventListener("keydown",event=>{
        if(event.key==="Enter"||event.key===" "){event.preventDefault();this._goPage("forecast");}
      });
    }
    add(head,hr);add(table,head);
    const body=el("tbody");
    const r1=el("tr","flowNumbers");
    for(const cell of [
      fmtPower(solar),fmtPower(home),fmtPower(battery),
      fmtPower(imp===null&&exp===null?null:Math.max(imp||0,exp||0)),
      values.outlook===null?"—":fmtEnergy(values.outlook)+" Today"
    ]) add(r1,el("td",null,cell));
    const r2=el("tr");
    for(const cell of [
      solar===null?"—":"Generating",
      home===null?"—":"Using",
      batteryStatus,
      gridStatus,
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
    const monitorToday={
      solar:nativeTodayEnergy(hass,"solar"),
      home:nativeTodayEnergy(hass,"home"),
      charge:nativeTodayEnergy(hass,"battery_charge"),
      discharge:nativeTodayEnergy(hass,"battery_discharge")
    };
    const costToday=this._costState()?.attributes?.today||{};
    const gridToday={
      import:Number.isFinite(costToday.import_kwh)&&costToday.import_kwh>=0?
        costToday.import_kwh:null,
      export:Number.isFinite(costToday.export_kwh)&&costToday.export_kwh>=0?
        costToday.export_kwh:null
    };
    const expectedByNow=typeof model.today==="number"&&
      typeof model.remaining_today==="number"?
      Math.max(0,model.today-model.remaining_today):null;
    const totalsRow=el("tr","flowDailyTotals");
    const detailCell=(label,rows,note)=>{
      const td=el("td");
      const labelEl=el("strong","flowDailyLabel",label);
      add(td,labelEl);
      for(const [name,value] of rows){
        const item=el("div","flowDailyLine");
        if(name)add(item,el("span","flowDailyName",name));
        add(item,el("b",null,fmtTodayKwh(value)));
        td.append(item);
      }
      if(note)td.title=note;
      return td;
    };
    add(totalsRow,
      detailCell("Today so far",[["Generated",monitorToday.solar]],
        "Inverter daily solar generation counter (kWh)"),
      detailCell("Today so far",[["Used",monitorToday.home]],
        "Inverter daily home consumption counter (kWh)"),
      detailCell("Today so far",[
        ["Charged",monitorToday.charge],
        ["Discharged",monitorToday.discharge]],
        "Separate inverter daily charged and discharged energy counters (kWh)"),
      detailCell("Today so far",[
        ["Imported",gridToday.import],
        ["Exported",gridToday.export]],
        "Estimated from recorded grid power since monitoring started today; provisional direction and coverage"),
      detailCell("Forecast by now",[["Expected",expectedByNow]],
        "Today's modeled full-day forecast minus remaining expected energy. Not measured generation")
    );
    add(body,r1,r2,r3,totalsRow);add(table,body);add(tableWrap,table);
    // Battery first: mode, SOC, and stored energy above the power bars.
    if(values.soc!==null){
      const socBox=el("div","socFlow");
      const top=el("div","socFlowTop");
      const mode=hass.states?.[SAFE_ENERGY_IDS.safeMode]?.state;
      const status=mode && !["unknown","unavailable"].includes(mode)?
        mode+" · ":"";
      add(top,el("span",null,"Battery"),
        el("strong",null,status+values.soc.toFixed(1)+"% · "+
          fmtEnergy(values.stored)+" stored"));
      const track=el("div","flowGraphTrack");
      const fill=el("div","flowGraphFill");
      fill.style.width=Math.max(0,Math.min(100,values.soc))+"%";
      track.append(fill);add(socBox,top,track);add(panel,socBox);
    }
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
    add(panel,tableWrap);
    // Keep forecast values in the table clickable as requested.
    for(const tr of [r1,r2,r3,totalsRow]){
      const cell=tr.lastElementChild;
      if(cell){
        cell.style.cursor="pointer";cell.title="View solar forecast";
        cell.addEventListener("click",()=>this._goPage("forecast"));
      }
    }
    add(panel,this._historyChart());
    add(panel,el("div","flowFoot",
      "Today kWh: inverter daily counters; grid kWh is a partial-coverage power-integrated estimate. "+
      "Forecast by now is modeled, not measured. Grid import/export direction is provisional. "+
      "This panel is read-only; TOU control actions are separate."+
      (custom?" Forecast values use your saved solar layout.":"")));
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
    const nav=el("nav","sajNav");
    nav.setAttribute("aria-label","SAJ dashboard pages");
    for(const [id,title] of [["control","Energy & controls"],["cost","Costs & savings"],["forecast","Solar forecast"]]){
      const button=el("button",null,title);
      button.type="button";
      if(this._page===id)button.setAttribute("aria-current","page");
      button.addEventListener("click",()=>this._goPage(id));
      nav.append(button);
    }
    add(card,nav);
    if(this._page==="forecast"){
      add(card,this._forecastPage());
      return;
    }
    if(this._page==="cost"){
      add(card,this._costPage());
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
    const right=el("div","readbackRight");
    add(right,el("span","muted",
      "Last verified: "+formatLocalTime(e.sync_status?.attributes.last_verified_read)));
    const reload=el("button","readbackRefresh",
      this._refreshBusy?"⟳ Refreshing…":"⟳ Refresh / reload data");
    reload.type="button";
    reload.title="Request fresh inverter settings and SAJ Safe Monitor data";
    reload.setAttribute("aria-label","Refresh inverter and live energy readings");
    reload.disabled=this._refreshBusy||this._modeBusy||this._fallbackBusy||
      this._scheduleWriteBusy||this._previewBusy;
    reload.addEventListener("click",()=>this._refreshMode(group));
    add(right,reload);
    add(status,statusIndicator,right);
    add(card,status);
    if(this._refreshNotice){
      const notice=el("div","readbackNotice "+
        (this._refreshNoticeError?"bad":"okay"),this._refreshNotice);
      notice.setAttribute("role","status");
      add(card,notice);
    }
    add(card,this._energyOverview());
    add(card,this._costOverview());
    if (!this._drafts.has(group.id)) this._drafts.set(group.id,cloneDraft(group));
    const draft=this._drafts.get(group.id);
    const meta=el("section","controlPanel");
    const metaHead=el("div","controlPanelHead");
    const liveMode=e.operating_mode?.state||"Unavailable";
    const outsideMode=e.outside_schedule?.state||"Unavailable";
    const states=el("div","controlSummary");
    const modeStatus=el("span","summaryState");
    add(modeStatus,el("span","summaryLabel","Operating"),
      el("strong",null,liveMode));
    const fallbackStatus=el("span","summaryState");
    add(fallbackStatus,el("span","summaryLabel","Outside TOU"),
      el("strong",null,outsideMode));
    add(states,modeStatus,fallbackStatus);
    add(metaHead,el("h3",null,"Inverter controls"),states);
    add(meta,metaHead);
    const controlColumns=el("div","controlColumns");
    const modepane=el("div","controlCell");
    const modeHeading=el("div","controlSubhead");
    add(modeHeading,el("h4",null,"Operating mode"));
    add(modepane,modeHeading);
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
    add(modepane,controls,
      el("p","muted controlHint",
        this._modeBusy?"Applying and verifying mode; do not click again.":
        blockers.length?"Live switch blocked: "+blockers.join("; ")+
          ". Use Refresh / reload data above.":
        "Mode changes are verified by direct Modbus readback. elekeeper may lag."));
    if (this._modeFeedback) {
      add(modepane,el("div","liveResult "+(this._modeFeedbackError?"bad":"okay"),this._modeFeedback));
    }
    const fallbackPane=el("div","controlCell");
    const fallbackHeading=el("div","controlSubhead");
    add(fallbackHeading,el("h4",null,"Outside TOU windows"));
    add(fallbackPane,fallbackHeading);
    const fallbackRaw=e.outside_schedule?.attributes.raw_fallback_code;
    // Native Windows/Brave <select> popups sometimes ignore dark styling.
    // An accessible in-card menu keeps BOTH the closed control and popup dark.
    const fallbackMenu=el("div","fallbackMenu");
    const fallbackTrigger=el("button","fallbackTrigger");
    fallbackTrigger.type="button";
    fallbackTrigger.setAttribute("aria-label","Outside TOU windows setting");
    fallbackTrigger.setAttribute("aria-haspopup","listbox");
    fallbackTrigger.setAttribute("aria-expanded","false");
    add(fallbackTrigger,el("span",null,fallbackRaw===0?"Standby":"Self-consumption"),
      el("span","fallbackChevron","⌄"));
    const fallbackOptions=el("div","fallbackOptions");
    fallbackOptions.setAttribute("role","listbox");
    fallbackOptions.setAttribute("aria-label","Outside TOU windows choices");
    fallbackOptions.hidden=true;
    const fallbackReadAt=e.outside_schedule?.attributes.last_verified_read;
    const fallbackAge=fallbackReadAt?
      (Date.now()-new Date(fallbackReadAt).getTime())/1000:Infinity;
    fallbackTrigger.disabled=![0,1].includes(fallbackRaw) || ![0,1].includes(modeValue) ||
      !good || this._fallbackBusy || this._modeBusy || this._scheduleWriteBusy ||
      !Number.isFinite(fallbackAge) || fallbackAge<0 || fallbackAge>180;
    const toggleMenu=open=>{
      fallbackOptions.hidden=!open;
      fallbackTrigger.setAttribute("aria-expanded",String(open));
      fallbackMenu.classList.toggle("open",open);
    };
    for(const [raw,label] of [[1,"Self-consumption"],[0,"Standby"]]){
      const option=el("button","fallbackOption",label);
      option.type="button";
      option.setAttribute("role","option");
      option.setAttribute("aria-selected",String(raw===fallbackRaw));
      option.disabled=raw===fallbackRaw;
      option.addEventListener("click",()=>{
        toggleMenu(false);
        fallbackTrigger.focus();
        if(raw!==fallbackRaw)this._changeOutsideTOU(group,raw);
      });
      fallbackOptions.append(option);
    }
    fallbackTrigger.addEventListener("click",()=>{
      if(!fallbackTrigger.disabled)toggleMenu(fallbackOptions.hidden);
    });
    fallbackMenu.addEventListener("keydown",ev=>{
      if(ev.key==="Escape"){
        toggleMenu(false);
        fallbackTrigger.focus();
        ev.preventDefault();
      }else if((ev.key==="ArrowDown"||ev.key==="ArrowUp")&&
               fallbackOptions.hidden){
        toggleMenu(true);
        ev.preventDefault();
        fallbackOptions.querySelector("button:not(:disabled)")?.focus();
      }
    });
    fallbackMenu.addEventListener("focusout",ev=>{
      if(!fallbackMenu.contains(ev.relatedTarget))toggleMenu(false);
    });
    add(fallbackMenu,fallbackTrigger,fallbackOptions);
    add(fallbackPane,fallbackMenu,
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
    add(sectionHead,el("h3",null,"Charging & discharging"),
      draft.changed?el("span","unsavedPill","● Unsaved changes"):
      el("span","muted","7 slots available per direction"));
    add(card,sectionHead);
    const columns=el("div","grid scheduleGrid");
    add(columns,this.scheduleSection(group,"charge",draft),this.scheduleSection(group,"discharge",draft));
    add(card,columns);
    if (draft.changed) add(card,el("div","draftNotice",
      "Draft only — nothing changes on the inverter until Save is confirmed."));
    const footer=el("div","row scheduleActions");
    const reset=el("button","secondaryAction","↶ Reload from inverter");
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
    const helper=el("p","scheduleFootnote",
      "Power (W) is estimated. Saves are confirmed and verified. "+
      "Interrupted writes may leave partial settings; check elekeeper before retrying.");
    helper.title="Schedule changes are written one register at a time, not atomically. "+
      "Overnight periods use the Split overnight option. Weekend day bits "+
      "are inferred from combined Saturday+Sunday readings.";
    add(card,helper);
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
    if(this._refreshBusy||this._modeBusy||this._fallbackBusy||
       this._scheduleWriteBusy||this._previewBusy)return;
    this._refreshBusy=true;
    this._refreshNotice="Refreshing inverter and energy data…";
    this._refreshNoticeError=false;this.render();
    const failures=[];
    try{
      // Explicitly request new data from BOTH read-only sources. The TOU
      // preview refreshes the TOU coordinator without sending any write.
      const data={target_mode:"time_of_use"};
      if(group.id && !group.id.startsWith("sensor."))data.entry_id=group.id;
      try {
        const result=await this._hass.callWS({
          type:"call_service",domain:"saj_h2_control_enhanced",
          service:"preview_mode_change",service_data:data,return_response:true
        });
        const report=result?.response||result;
        if(report?.status!=="DRY_RUN_ONLY"||report.write_sent!==false)
          throw new Error("No safe inverter refresh acknowledgement");
      } catch(err) {
        failures.push("Inverter: "+(err?.message||String(err)));
      }
      // The safe monitor has one live-data coordinator and a separate
      // forecast coordinator. Refresh ONE representative from each, not every
      // sensor (which could issue redundant Modbus scans).
      const liveId=["solar","home","battery","soc"]
        .map(key=>SAFE_ENERGY_IDS[key])
        .find(id=>Boolean(this._hass.states?.[id]));
      const forecastId=["outlook","remaining","tomorrow"]
        .map(key=>SAFE_ENERGY_IDS[key])
        .find(id=>Boolean(this._hass.states?.[id]));
      const entityIds=[...new Set([liveId,forecastId].filter(Boolean))];
      if(entityIds.length){
        try {
          await this._hass.callService("homeassistant","update_entity",{
            entity_id:entityIds
          });
        } catch(err) {
          failures.push("Energy monitor: "+(err?.message||String(err)));
        }
      } else {
        failures.push("SAJ Safe Monitor entities not found");
      }
      this._refreshNotice=failures.length?
        "Refresh partly completed: "+failures.join("; ")+
        ". Check readings before relying on them.":
        "Refresh requested. Readings will update as sensors respond; no settings changed.";
      this._refreshNoticeError=failures.length>0;
    } finally {
      this._refreshBusy=false;
      this.render();
    }
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
    add(header,el("h3",null,title+" · "+rows.length+"/7"));
    const addButton=el("button","addSchedule","+ Add "+direction);
    addButton.type="button";
    addButton.disabled=rows.length>=7 || !isValid(state);
    addButton.title="Create a new "+direction+" period (maximum seven)";
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
    add(header,addButton);add(pane,header);
    if (!isValid(state)) add(pane,el("p","bad","Device schedule data unavailable."));
    if (!rows.length) add(pane,el("p","muted emptySchedule",
      "No "+direction+" periods set"));
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
