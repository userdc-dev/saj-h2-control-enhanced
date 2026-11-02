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
  ".forecastDay{display:grid;grid-template-columns:minmax(75px,120px) 1fr 90px;align-items:center;gap:8px;font-size:12px}",
  ".forecastTrack{height:12px;border-radius:8px;background:var(--divider-color,#444);overflow:hidden}",
  ".forecastFill{height:100%;background:var(--primary-color,#16b9b1);border-radius:8px}",
  ".forecastSettings{margin:18px 0;padding:16px;border:1px solid var(--divider-color,#555);border-radius:12px}",
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
  ".energyEntity{font-size:11px;color:var(--secondary-text-color,#bbb);overflow-wrap:anywhere;display:block}",
  ".costNotice{padding:10px 12px;border-left:3px solid var(--warning-color,#d6ae57);background:rgba(128,128,128,.035);border-radius:0 7px 7px 0;font-size:12px;line-height:1.65;margin:12px 0}",
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
    this._costSaving = false;
    this._costMessage = "";
    this._costError = false;
    this._forecastForm = null;
    this._forecastSaving = false;
    this._forecastMessage = "";
    this._forecastError = false;
    this._historyData = null;
    this._historyPending = false;
    this._historyError = "";
    this._historyHours = 24;
    this._historyVisible = {solar:true,home:true,battery:true,grid:true};
    this._historySignature = "";
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
        if(this._page==="cost"&&!this._costEditing&&!this._costSaving)this.render();
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
    if(!settings.configured)
      add(section,el("div","costNotice",
        "Example electricity prices are not your tariff. Open Costs & savings to enter your import rate, export credit or fee, and daily supply charge."));
    const today=state.attributes.today,month=state.attributes.month;
    const stats=el("div","costStatGrid");
    for(const [label,row,note] of [
      ["Today (tracked)",today,"Partial-day estimate"],
      ["This month (tracked)",month,"Partial-month estimate"]
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
      "Estimated grid flows are integrated from power readings; missing periods are excluded. "+
      "Signed rates are supported. Values are not a replacement for your retailer's bill."));
    return section;
  }
  _costPage(){
    const root=el("section");
    const header=el("div","forecastHeader");
    add(header,el("h2",null,"Costs & savings"),
      el("span","muted","Static tariffs · read-only estimates"));
    add(root,header);
    const state=this._costState();
    if(!state){
      add(root,el("p","costNotice",
        "The read-only SAJ H2 Safe Monitor must be installed, configured and running on the same inverter before cost and energy records appear. Settings are not available until then."));
      return root;
    }
    const data=state.attributes;
    const p=data.pricing||{};
    if(!p.configured)add(root,el("p","costNotice",
      "Prices below are EXAMPLE defaults, not your electricity plan. Please enter your actual import cost, export payment/fee and supply charge before interpreting estimated dollars."));
    const stats=el("div","costStatGrid");
    const rows=[
      ["Today · estimated net",data.today?.net_cost,"Partially recorded today"],
      ["Month · estimated net",data.month?.net_cost,"Partially recorded this month"],
      ["Today · self-supply & export value",data.today?.self_supply_estimated_benefit,
       "Illustrative combined benefit; solar and battery cannot be separated reliably"],
      ["Today · battery discharge potential",data.today?.battery_discharge_illustrative_value,
       "Gross illustration only; NOT additional savings to add to the combined benefit"]
    ];
    for(const [label,value,note] of rows){
      const stat=el("div","costStat");
      add(stat,el("span","muted",label),
        el("strong",null,p.configured?this._currency(value):"—"),
        el("small",null,note));
      stats.append(stat);
    }
    add(root,stats);
    const details=el("div","costDetail");
    for(const [label,row] of [["Today (available coverage)",data.today],
                              ["This month (available coverage)",data.month]]){
      const box=el("div","pane");
      add(box,el("h3",null,label));
      if(!row){
        add(box,el("p","muted","Waiting for recorded grid power readings."));
      }else for(const [k,v,unit] of [
        ["Grid imported",row.import_kwh,"kWh"],
        ["Grid exported",row.export_kwh,"kWh"],
        ["Solar generated (observed intervals)",row.solar_kwh,"kWh"],
        ["Home use (observed intervals)",row.home_kwh,"kWh"],
        ["Grid import cost",row.import_cost,"currency"],
        ["Grid export credit / fee",row.export_credit,"currency"],
        ["Standing charge (prorated)",row.supply_cost,"currency"]
      ]){
        add(box,el("p",null,k+": "+(typeof v==="number"?
          unit==="currency"?this._currency(v):v.toFixed(2)+" "+unit:"—"));
      }
      if(row)add(box,el("p","muted",
        "Recorded coverage: "+(row.coverage_seconds/3600).toFixed(1)+
        " hours. No missing past intervals are filled in."));
      details.append(box);
    }
    add(root,details);
    if(!this._costForm)this._costForm={
      import_rate:Number(p.import_rate??0.35),
      export_rate:Number(p.export_rate??0.05),
      daily_supply:Number(p.daily_supply??1.0)
    };
    const form=this._costForm;
    const pane=el("section","costSettings");
    add(pane,el("h3",null,"Electricity price settings"));
    add(pane,el("p","muted",
      "Static rates in AUD. Enter a positive import rate when you PAY for grid energy; negative if you are PAID to import. "+
      "Positive export rate means the retailer pays you; negative means you pay a fee to export. Signed daily supply charges are also supported."));
    const inputs=el("div","costInputs");
    const field=(label,key,step)=>{
      const holder=el("label");
      add(holder,el("span",null,label));
      const input=el("input");
      input.type="number";input.step=String(step);
      input.min="-100";input.max="100";
      input.value=String(form[key]);
      input.setAttribute("aria-label",label);
      input.addEventListener("focus",()=>this._costEditing=true);
      input.addEventListener("input",()=>{
        const n=Number(input.value);
        if(input.value!==""&&Number.isFinite(n))form[key]=n;
      });
      input.addEventListener("blur",()=>this._costEditing=false);
      holder.append(input);
      return holder;
    };
    add(inputs,
      field("Grid import cost (AUD/kWh)","import_rate",0.001),
      field("Grid export payment (AUD/kWh)","export_rate",0.001),
      field("Daily supply charge (AUD/day)","daily_supply",0.01));
    add(pane,inputs);
    const save=el("button","primaryAction",
      this._costSaving?"Saving…":"Save electricity prices");
    save.type="button";save.disabled=this._costSaving;
    save.addEventListener("click",()=>this._saveCostSettings());
    add(pane,save);
    if(this._costMessage)
      add(pane,el("p",this._costError?"bad":"okay",this._costMessage));
    add(pane,el("p","historyFoot",
      "Dynamic tariffs (including future AEMO integration) are not enabled yet. "+
      "No price changes alter inverter operating modes, TOU schedules or battery controls."));
    add(root,pane);
    add(root,el("p","costNotice",
      "These are estimates, not bill calculations. Grid direction is not yet independently validated. "+
      "Self-supply value assumes home demand would otherwise be imported at a flat rate. "+
      "Battery discharge value can overlap solar benefit or represent grid-charged energy; do not add the two figures together. "+
      "Supply charges count monitored hours, not an assumed full day or full month."));
    add(root,this._energySetupGuide());
    return root;
  }
  async _saveCostSettings(){
    const form=this._costForm;
    if(!form||Object.values(form).some(v=>!Number.isFinite(v)||v< -100||v>100)){
      this._costMessage="Enter valid signed rates between −100 and +100.";
      this._costError=true;this.render();return;
    }
    this._costSaving=true;this._costEditing=false;this._costMessage="";
    this.render();
    try{
      const data={...form};
      if(this._selected&&!this._selected.startsWith("sensor."))
        data.entry_id=this._selected;
      const answer=await this._hass.callWS({
        type:"call_service",domain:"saj_h2_control_enhanced",
        service:"save_cost_settings",service_data:data,return_response:true
      });
      this._costMessage="Rates saved; cost calculations updated. No inverter writes.";
      this._costError=false;this._costForm=null;
    }catch(error){
      this._costMessage="Could not save rates: "+(error?.message||String(error));
      this._costError=true;
    }finally{
      this._costSaving=false;this.render();
    }
  }
  _energySetupGuide(){
    const section=el("section","energyGuide");
    add(section,el("h3",null,"Home Assistant Energy — sensor guide"));
    add(section,el("p","muted",
      "Open Home Assistant Settings → Dashboards → Energy, and choose sensors by the names below. "+
      "Energy totals (kWh) and instantaneous power (W) are distinct."));
    const descriptions=[
      ["Electricity grid imported","grid_import_energy_estimate",
        "Estimated cumulative kWh from sampled signed grid power — provisional polarity"],
      ["Electricity grid exported","grid_export_energy_estimate",
        "Estimated cumulative kWh, not a certified grid meter"],
      ["Solar production energy","solar_production_energy",
        "Inverter lifetime kWh counter"],
      ["Solar production power","solar_production_power",
        "Instantaneous W, not cumulative kWh"],
      ["Solar production forecast",null,
        "Editable solar forecast on the separate Solar forecast tab; not metered generation"],
      ["Battery energy charged","battery_charged_energy",
        "Inverter lifetime kWh counter"],
      ["Battery energy discharged","battery_discharged_energy",
        "Inverter lifetime kWh counter"],
      ["Battery state of charge","battery_state_of_charge",
        "Battery percentage (%)"],
      ["Battery power","battery_power","Signed W; charging negative"]
    ];
    const list=el("ul");
    const entities=Object.values(this._hass?.states||{});
    for(const [title,key,explain] of descriptions){
      const item=el("li");
      add(item,el("strong",null,title),el("div","muted",explain));
      if(key){
        const source=entities.find(s=>s.attributes?.saj_energy_role===key&&
          s.entity_id && s.attributes?.friendly_name);
        if(source)add(item,el("code","energyEntity",source.entity_id));
      }
      list.append(item);
    }
    add(section,list);
    add(section,el("p","historyFoot",
      "All sensor aliases use correct HA energy/power/battery device classes. "+
      "The estimated grid kWh counters begin accumulating only once monitoring is active. "+
      "Confirm grid polarity against your utility meter before relying on them for Energy totals."));
    return section;
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
    const daily=Array.isArray(data.daily)?data.daily:[];
    const heading=el("h3",null,"Next seven days");add(section,heading);
    const days=el("div","forecastDays");
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
      days.append(row);
    }
    if(!daily.length)add(days,el("p","muted","Forecast pending weather service response."));
    add(section,days);
    const hourly=Array.isArray(data.hourly_today)?data.hourly_today:[];
    add(section,el("h3",null,"Actual vs projected · Today"));
    add(section,this._actualProjectedChart(hourly));
    add(section,el("h3",null,"Today · hourly PV forecast"));
    if(hourly.length){
      const plot=el("div","forecastDays");
      const peak=Math.max(1,...hourly.map(h=>Number(h.kwh)||0));
      for(const h of hourly){
        const row=el("div","forecastDay");
        const track=el("div","forecastTrack");
        const fill=el("div","forecastFill");
        fill.style.width=Math.max(0,Math.min(100,(Number(h.kwh)||0)/peak*100))+"%";
        track.append(fill);
        add(row,el("span",null,h.hour),track,
          el("span",null,(Number(h.kwh)||0).toFixed(2)+" kWh"));
        plot.append(row);
      }
      add(section,plot);
    }else add(section,el("p","muted","Hourly weather forecast is unavailable."));
    const settings=this._forecastSettings();
    if(!this._forecastForm)this._forecastForm={
      groups:settings.groups.map(g=>({...g})),
      efficiency:settings.efficiency,ac_limit_kw:settings.ac_limit_kw
    };
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
    add(section,wrapper);
    return section;
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
    }catch(err){
      this._forecastError=true;
      this._forecastMessage="Forecast settings not saved: "+(err?.message||String(err));
    }finally{this._forecastSaving=false;this.render();}
  }
  _actualProjectedChart(hourly){
    const panel=el("section","forecastHistory actualForecast");
    if(!hourly.length){
      add(panel,el("p","muted","Hourly forecast data not yet available."));
      return panel;
    }
    const solarHistory=this._historyData?.solar||[];
    if(!this._historyData&&!this._historyPending)this._loadHistory();
    const now=new Date();
    const midnight=new Date(now);
    midnight.setHours(0,0,0,0);
    const midnightMs=midnight.getTime();
    const projection=[];
    let accumulated=0;
    const ordered=hourly.slice().sort((a,b)=>a.hour.localeCompare(b.hour));
    projection.push({hour:0,kwh:0});
    for(const record of ordered){
      const h=Number(record.hour.slice(0,2)),minute=Number(record.hour.slice(3,5));
      if(!Number.isFinite(h)||!Number.isFinite(minute))continue;
      accumulated+=Math.max(0,Number(record.kwh)||0);
      projection.push({hour:h+minute/60+1,kwh:accumulated});
    }
    const actual=[{hour:0,kwh:0}];
    let total=0,prior=null;
    for(const sample of solarHistory){
      if(sample.t<midnightMs||sample.t>Date.now())continue;
      if(prior&&sample.t-prior.t<=30*60000){
        total+=Math.max(0,(Math.max(0,sample.y)+Math.max(0,prior.y))/2)*
          (sample.t-prior.t)/3600000000;
      }
      actual.push({hour:(sample.t-midnightMs)/3600000,kwh:total});
      prior=sample;
    }
    const peak=Math.max(1,...projection.map(p=>p.kwh),...actual.map(p=>p.kwh));
    const ns="http://www.w3.org/2000/svg";
    const svg=document.createElementNS(ns,"svg");
    svg.setAttribute("viewBox","0 0 920 280");
    svg.setAttribute("class","historySvg");
    svg.setAttribute("role","img");
    svg.setAttribute("aria-label","Cumulative actual solar production compared with projected PV output today");
    const shape=(tag,attrs,content)=>{
      const node=document.createElementNS(ns,tag);
      for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));
      if(content!==undefined)node.textContent=content;
      svg.append(node);return node;
    };
    const x=h=>50+Math.max(0,Math.min(24,h))/24*820;
    const y=kwh=>235-Math.max(0,Math.min(1,kwh/peak))*205;
    for(let i=0;i<=4;i++){
      const yy=30+(205*i/4);
      shape("line",{x1:50,y1:yy,x2:870,y2:yy,stroke:"currentColor","stroke-opacity":".15"});
      shape("text",{x:43,y:yy+4,fill:"currentColor","text-anchor":"end","font-size":11},
        (peak*(4-i)/4).toFixed(0));
    }
    for(let h=0;h<=24;h+=6)shape("text",{
      x:x(h),y:260,fill:"currentColor","font-size":12,"text-anchor":"middle"},h+":00");
    for(const [points,color] of [[projection,"#dfb548"],[actual,"#529ce7"]]){
      if(points.length<2)continue;
      const d=points.map((p,i)=>(i?"L":"M")+x(p.hour).toFixed(1)+","+
        y(p.kwh).toFixed(1)).join(" ");
      shape("path",{d,stroke:color,"stroke-width":2.5,fill:"none",
        "stroke-linecap":"round","stroke-linejoin":"round"});
    }
    add(panel,svg,el("div","historyFoot",
      "● Projected PV production (yellow)  ● Recorded actual PV production (blue) · kWh accumulated today. "+
      "Actual is integrated from Home Assistant history and can be incomplete if recordings have gaps; "+
      "the model's AC limit is not applied to PV-side production."));
    if(!solarHistory.length)add(panel,el("p","muted",
      "Actual production graph will appear when Home Assistant recorded history becomes available."));
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
    add(body,r1,r2,r3);add(table,body);add(tableWrap,table);
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
    for(const tr of [r1,r2,r3]){
      const cell=tr.lastElementChild;
      if(cell){
        cell.style.cursor="pointer";cell.title="View solar forecast";
        cell.addEventListener("click",()=>this._goPage("forecast"));
      }
    }
    add(panel,this._historyChart());
    add(panel,el("div","flowFoot",
      "Forecast is an estimate; grid import/export direction is provisional. "+
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
