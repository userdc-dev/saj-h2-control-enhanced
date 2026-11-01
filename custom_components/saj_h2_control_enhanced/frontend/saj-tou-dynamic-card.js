/* SAJ H2 TOU dynamic card v0.2 preview.
 * Displays inverter-saved schedules from actual HA entities, discovers all
 * installed SAJ TOU readback devices by entity attributes, no hardcoded IDs.
 * All sliders/time/day/mode controls are LOCAL DRAFTS ONLY: no service calls,
 * no network, no writes, and no permanent storage of drafts.
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
].join("");
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = String(text);
  return node;
};
const add = (parent, ...children) => {children.forEach(c => parent.append(c)); return parent;};
const isValid = state => state && !["unknown","unavailable"].includes(state.state);
const roles = ["operating_mode","outside_schedule","charge_schedules","discharge_schedules","sync_status"];
const suffixes = {
  operating_mode:"_operating_mode",
  outside_schedule:"_outside_schedule_behaviour",
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
      start:cleanTime(v.start),end:cleanTime(v.end),
      percent:Math.max(0,Math.min(100,Number(v.power_percent_raw)||0)),
      dayMask:Number(v.weekday_mask_raw)||0,
      days: ((Number(v.weekday_mask_raw)||0) & ~20) === 0 ?
        [...((Number(v.weekday_mask_raw)||0)&4 ? ["Wed"] : []),
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
    add(top,el("h2",null,"Battery time-of-use"),el("span","pill","Device readback · Preview v0.2.3"));
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
    const modeSel=this.choice(["Self-consumption","Time-of-use"],draft.mode,v=>{draft.mode=v;draft.changed=true;});
    add(modepane,modeSel,el("p","muted","Mode selection is local preview only."));
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
    add(card,el("div","warn","Local draft only: sliders, times and weekday selectors DO NOT save to SAJ or eLEKeeper. Friday and Wednesday weekday bits are confirmed. Charge power 50% = 4950 W was confirmed; remaining charge powers and other weekday bits still require testing. Device settings follow HA readback unless you have an edited draft. Click Reload draft to accept external changes."));
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
      if (row.original && (row.dayMask & ~20)) add(container,el("div","saved","Device weekday mask: "+row.dayMask+" (unverified weekday bits present; preview cannot safely show every day)"));
      const times=el("div","inputs");
      for (const key of ["start","end"]) {
        const wrapper=el("label","muted",key==="start"?"Start · 24h":"End · 24h");
        const field=el("input","time24");field.type="text";field.inputMode="numeric";field.maxLength=5;
        field.placeholder="HH:MM";field.pattern="(?:[01][0-9]|2[0-3]):[0-5][0-9]";field.value=row[key];
        field.setAttribute("aria-label",key+" 24-hour time HH:MM");
        field.addEventListener("change",()=>{
          const next=field.value.trim();
          if(!is24Hour(next)){
            field.value=row[key];field.title="Use 24-hour HH:MM, e.g. 22:40";
            return;
          }
          row[key]=next;draft.changed=true;field.title="";
        });
        add(wrapper,field);add(times,wrapper);
      }
      add(container,times);
      const actualSlots=(state?.attributes.schedules||[]);
      const saved=actualSlots.find(item => Number(item.slot) === index+1);
      if (saved) add(container,el("div","saved","Saved on inverter: "+saved.start+"–"+saved.end+" · "+(saved.power_conversion_verified ? saved.power_watts_saj_display+" W" : saved.power_percent_raw+"% raw (W unverified)")));
      const power=el("div","row");
      const label=el("span","muted","Draft power");
      const slider=el("input");slider.type="range";slider.min="0";slider.max="100";slider.step="1";slider.value=String(row.percent);
      const previewText = () => direction==="discharge" ? (row.percent*99)+" W" : row.percent===50 ? "4950 W (verified)" : row.percent+"% (W unverified)";
      const display=el("strong",null,previewText());
      slider.addEventListener("input",()=>{row.percent=Number(slider.value);draft.changed=true;display.textContent=previewText()});
      add(power,label,slider,display);add(container,power);
      const dayrow=el("div","days");
      DAYS.forEach(day=>{
        const label=el("label","day");
        const cb=el("input");cb.type="checkbox";cb.checked=row.days.includes(day);
        cb.addEventListener("change",()=>{
          row.days=cb.checked ? [...new Set([...row.days,day])] : row.days.filter(d=>d!==day);
          draft.changed=true;
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
      rows.push({start:"00:00",end:"00:00",percent:0,dayMask:0,days:[],original:false});
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
  description:"Auto-discover device-backed TOU schedules. Edit local drafts; no writes.",
  preview:true
});
})();
