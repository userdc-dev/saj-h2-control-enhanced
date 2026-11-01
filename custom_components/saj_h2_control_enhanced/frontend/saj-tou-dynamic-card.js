/* SAJ H2 TOU dynamic card v0.2 preview.
 * Displays inverter-saved schedules from actual HA entities, discovers all
 * installed SAJ TOU readback devices by entity attributes, no hardcoded IDs.
 * Only two explicitly confirmed operating-mode buttons invoke a live HA action.
 * All schedule, power, time, and fallback controls remain LOCAL DRAFTS ONLY.
 */
(() => {
"use strict";
const TAG = "saj-tou-dynamic-card";
if (customElements.get(TAG)) return;
const DAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
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
      days: ((Number(v.weekday_mask_raw)||0) & ~31) === 0 ?
        [...((Number(v.weekday_mask_raw)||0)&1 ? ["Mon"] : []),
         ...((Number(v.weekday_mask_raw)||0)&2 ? ["Tue"] : []),
         ...((Number(v.weekday_mask_raw)||0)&4 ? ["Wed"] : []),
         ...((Number(v.weekday_mask_raw)||0)&8 ? ["Thu"] : []),
         ...((Number(v.weekday_mask_raw)||0)&16 ? ["Fri"] : [])] : [],
      original:true
    }));
  }
  return {
    mode: e.operating_mode && e.operating_mode.state==="Time-of-use" ? "Time-of-use" : "Self-consumption",
    fallback: e.outside_schedule && e.outside_schedule.state==="Standby" ? "Standby" : "Self-consumption",
    charge:rows("charge_schedules"),discharge:rows("discharge_schedules"),
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
    this._modeBusy = false;
    this._modeFeedback = "";
    this._modeFeedbackError = false;
    this._modeBusyEntry = "";
    this._refreshBusy = false;
    this._schedulePreview = new Map();
    this._previewBusy = false;
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
    if (sig!==this._lastSignature) {
      this._lastSignature=sig;
      // Follow external eLEKeeper changes unless the user is editing a draft.
      devices.forEach(g=>{
        const existing=this._drafts.get(g.id);
        if (existing && !existing.changed) this._drafts.set(g.id,cloneDraft(g));
      });
      this.render();
    }
  }
  getCardSize() {return 7;}
  getStubConfig() {return {};}
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
    const top=el("div","top");
    add(top,el("h2",null,"Battery time-of-use"),el("span","pill","Live mode control · Schedules preview"));
    add(card,top);
    if (!group) {
      add(card,el("p","empty","No SAJ H2 TOU devices found. Install the read-only TOU integration and check its schedule entities."));
      return;
    }
    const select=el("select");
    devices.forEach((g,index)=>{
      const opt=el("option",null, (g.entities.operating_mode?.attributes.friendly_name||"SAJ H2 TOU").replace(/ Operating mode$/i,"") + (devices.length>1?" · Device "+(index+1):""));
      opt.value=g.id;opt.selected=g.id===group.id;select.append(opt);
    });
    select.addEventListener("change",e=>{this._selected=e.target.value;this.render()});
    const source=el("div","row");
    add(source,el("span","muted","Detected TOU device"),select);add(card,source);
    const e=group.entities;
    const good=roles.every(r => isValid(e[r]));
    const status=el("div","row");
    add(status,el("span",good?"okay":"bad",good?"● Settings read from device":"● Readback unavailable"),
      el("span","muted","Last read: "+formatLocalTime(e.sync_status?.attributes.last_verified_read)));
    add(card,status);
    if (!this._drafts.has(group.id)) this._drafts.set(group.id,cloneDraft(group));
    const draft=this._drafts.get(group.id);
    const meta=el("div","grid");
    const modepane=el("section","pane");
    add(modepane,el("h3",null,"Operating mode"),
      el("div","saved","Device: "+(e.operating_mode?.state||"unknown")));
    const modeValue=e.operating_mode?.attributes.raw_mode_code;
    const freshTime=e.operating_mode?.attributes.last_verified_read;
    const ageSeconds=freshTime?(Date.now()-new Date(freshTime).getTime())/1000:Infinity;
    const canOperate=good && Number.isInteger(modeValue) &&
      (modeValue===0 || modeValue===1) &&
      e.outside_schedule?.attributes.raw_fallback_code===1 &&
      Number.isFinite(ageSeconds) && ageSeconds>=0 && ageSeconds<=180 &&
      !this._modeBusy && !draft.changed &&
      e.charge_count?.attributes.slot_enable_mask===1 &&
      e.discharge_count?.attributes.slot_enable_mask===1;
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
    if (e.outside_schedule?.attributes.raw_fallback_code!==1) blockers.push("fallback is not Self-consumption");
    if (!Number.isFinite(ageSeconds) || ageSeconds<0 || ageSeconds>180) blockers.push("readback older than 3 minutes");
    if (draft.changed) blockers.push("local draft modified");
    if (e.charge_count?.attributes.slot_enable_mask!==1 ||
        e.discharge_count?.attributes.slot_enable_mask!==1) blockers.push("schedule masks not [1,1]");
    const refresh=el("button",null,this._refreshBusy?"Refreshing…":"Refresh inverter state");
    refresh.type="button";refresh.disabled=this._refreshBusy||this._modeBusy;
    refresh.addEventListener("click",()=>this._refreshMode(group));
    add(modepane,controls,refresh,
      el("p","muted",
        this._modeBusy?"Applying and verifying mode; do not click again.":
        blockers.length?"Live switch blocked: "+blockers.join("; ")+". Refresh to recheck.":
        "Live mode control uses a confirmed one-shot Modbus action. eLEKeeper overview can lag."));
    if (this._modeFeedback) {
      add(modepane,el("div","liveResult "+(this._modeFeedbackError?"bad":"okay"),this._modeFeedback));
    }
    const fallbackPane=el("section","pane");
    add(fallbackPane,el("h3",null,"Outside TOU windows"),
      el("div","saved","Device: "+(e.outside_schedule?.state||"unknown")));
    add(fallbackPane,this.choice(["Self-consumption","Standby"],draft.fallback,v=>{draft.fallback=v;draft.changed=true;}),
      el("p","muted","Self-consumption is the preferred default."));
    add(meta,modepane,fallbackPane);add(card,meta);
    const columns=el("div","grid");
    add(columns,this.scheduleSection(group,"charge",draft),this.scheduleSection(group,"discharge",draft));
    add(card,columns);
    if (draft.changed) add(card,el("div","warn","Unsaved local draft. Device values above continue updating, but preview edits are preserved until you click Reload draft."));
    const footer=el("div","row");
    const reset=el("button",null,"Reload draft from inverter");
    reset.addEventListener("click",()=>{this._drafts.set(group.id,cloneDraft(group));this.render();});
    const apply=el("button",null,"Apply to inverter · disabled");
    apply.disabled=true;
    add(footer,reset,apply);add(card,footer);
    const change=e.sync_status?.attributes.last_changes;
    if (Array.isArray(change)&&change.length) {
      add(card,el("p","muted","Last detected change: "+change.join("; ")));
    }
    add(card,el("div","warn","Local draft only: sliders, times and weekday selectors DO NOT save to SAJ or eLEKeeper. Monday through Friday weekday bits are confirmed, including Tuesday+Thursday together. Charge power at raw 50 = 4950 W and raw 70 = 6930 W is app-confirmed; other raw levels are modeled at 99 W per unit. Other weekday bits still require testing. Device settings follow HA readback unless you have an edited draft. Click Reload draft to accept external changes."));
  }
  async _refreshMode(group) {
    if(this._refreshBusy||this._modeBusy)return;
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
    if (this._modeBusy) return;
    const current=group.entities.operating_mode?.attributes.raw_mode_code;
    const fallback=group.entities.outside_schedule?.attributes.raw_fallback_code;
    const charge=group.entities.charge_count?.attributes.slot_enable_mask;
    const discharge=group.entities.discharge_count?.attributes.slot_enable_mask;
    const source=group.entities.operating_mode?.attributes.last_verified_read;
    const age=source ? (Date.now()-new Date(source).getTime())/1000 : Infinity;
    const draft=this._drafts.get(group.id);
    if (!Number.isInteger(current) || current!==1-target || fallback!==1 ||
        charge!==1 || discharge!==1 || !Number.isFinite(age) || age<0 ||
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
      "\nSaved schedules will not be edited. Have eLEKeeper available.")) return;
    const typed=window.prompt(
      "Type ONLY the confirmation phrase below (no quotes or extra characters):\n\n"+
      phrase,"");
    if (typed!==phrase) {
      this._modeFeedback="Cancelled: confirmation phrase did not match.";
      this._modeFeedbackError=true;this.render();return;
    }
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
        throw new Error("No verified device response. Do NOT retry automatically. Check eLEKeeper and Modbus.");
      }
      this._modeFeedback="Verified by Modbus: inverter now reports "+label+
        ". Schedules and fallback unchanged. eLEKeeper display may lag.";
      this._modeFeedbackError=false;
    } catch(error) {
      this._modeFeedbackError=true;
      this._modeFeedback="Unable to confirm mode change: "+
        (error?.message||String(error))+
        ". A write may already have been sent. Do NOT repeat the action. Check eLEKeeper.";
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
      const remove=el("button",null,"Remove draft");
      remove.addEventListener("click",()=>{rows.splice(index,1);draft.changed=true;this.render()});
      add(bar,el("strong",null,title+" "+(index+1)),remove);
      add(container,bar);
      if (row.original && (row.dayMask & ~31)) add(container,el("div","saved","Device weekday mask: "+row.dayMask+" (unverified weekday bits present; preview cannot safely show every day)"));
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
          }
          field.setCustomValidity("");
        });
        add(wrapper,field);add(times,wrapper);
      }
      add(container,times);
      const actualSlots=(state?.attributes.schedules||[]);
      const saved=actualSlots.find(item => Number(item.slot) === row.slotNumber);
      if (saved) add(container,el("div","saved","Saved on inverter: "+saved.start+"–"+saved.end+" · "+saved.power_watts_saj_display+" W"+(saved.power_conversion_verified ? " (paired)" : " (estimated)")));
      const previewButton=el("button",null,this._previewBusy?"Validating…":"Validate schedule draft (no write)");
      previewButton.type="button";
      previewButton.disabled=!saved||this._previewBusy||!row.original||!isValid(state) ||
        (row.savedStart===undefined);
      previewButton.addEventListener("click",()=>this._validateSchedule(group,direction,row,saved));
      add(container,previewButton);
      const previewKey=group.id+":"+direction+":"+row.slotNumber;
      const preview=this._schedulePreview.get(previewKey);
      if(preview) add(container,el("div","liveResult "+(preview.error?"bad":"okay"),preview.message));

      const power=el("div","row");
      const label=el("span","muted","Draft power");
      const slider=el("input");slider.type="range";slider.min="0";slider.max="100";slider.step="1";slider.value=String(row.percent);
      const previewText = () => (row.percent*99)+" W"+(direction==="charge" && ![50,70].includes(row.percent) ? " (estimated)" : "");
      const display=el("strong",null,previewText());
      slider.addEventListener("input",()=>{row.percent=Number(slider.value);draft.changed=true;this._schedulePreview.delete(group.id+":"+direction+":"+row.slotNumber);display.textContent=previewText()});
      add(power,label,slider,display);add(container,power);
      const dayrow=el("div","days");
      DAYS.forEach(day=>{
        const label=el("label","day");
        const cb=el("input");cb.type="checkbox";cb.checked=row.days.includes(day);
        cb.addEventListener("change",()=>{
          row.days=cb.checked ? [...new Set([...row.days,day])] : row.days.filter(d=>d!==day);
          draft.changed=true;
          this._schedulePreview.delete(group.id+":"+direction+":"+row.slotNumber);
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
      rows.push({slotNumber:null,start:"00:00",end:"00:00",percent:0,dayMask:0,days:[],original:false});
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
  description:"Confirmed live mode buttons, fresh readback refresh and safe schedule draft validation.",
  preview:true
});
})();
