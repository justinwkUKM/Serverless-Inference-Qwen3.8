const $ = (selector) => document.querySelector(selector);
const state = { messages: [], busy: false, webSearch: false, lastCompletedAt: Number(localStorage.getItem("lastCompletedAt") || 0), config: null };
const els = { prompt:$("#prompt"), send:$("#sendButton"), messages:$("#messages"), empty:$("#emptyState"), badge:$("#healthBadge"), metrics:$("#metricsPanel"), ttft:$("#ttft"), tps:$("#tps"), total:$("#totalTime"), tokens:$("#tokens"), kind:$("#requestKind"), note:$("#metricsNote"), fill:$("#timelineFill") };
let scrollFrame = 0;

function scrollToLatest(behavior = "auto") {
  if (scrollFrame) cancelAnimationFrame(scrollFrame);
  scrollFrame = requestAnimationFrame(() => {
    document.querySelector("footer").scrollIntoView({ behavior, block: "end" });
    scrollFrame = 0;
  });
}

function escapeHtml(value="") { return value.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]); }
function markdown(source="") {
  let text = escapeHtml(source);
  const blocks=[];
  text=text.replace(/```([\w+-]*)\n([\s\S]*?)```/g,(_,lang,code)=>{const id=blocks.push(`<pre><code data-lang="${lang}">${code.replace(/\n$/,"")}</code></pre>`)-1;return `\n@@BLOCK${id}@@\n`});
  text=text.replace(/^### (.+)$/gm,"<h3>$1</h3>").replace(/^## (.+)$/gm,"<h2>$1</h2>").replace(/^# (.+)$/gm,"<h1>$1</h1>");
  text=text.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  text=text.replace(/^(?:- .+(?:\n|$))+/gm,m=>`<ul>${m.trim().split("\n").map(x=>`<li>${x.slice(2)}</li>`).join("")}</ul>`);
  text=text.split(/\n{2,}/).map(p=>p.startsWith("<h")||p.startsWith("<ul")||p.startsWith("@@BLOCK")?p:`<p>${p.replace(/\n/g,"<br>")}</p>`).join("");
  return text.replace(/@@BLOCK(\d+)@@/g,(_,i)=>blocks[Number(i)]);
}

function addMessage(role, content="") {
  els.empty.classList.add("hidden");
  const node=document.createElement("article");node.className=`message ${role}`;
  node.innerHTML=`<div class="avatar">${role==="user"?"Y":"✦"}</div><div class="message-body"></div>`;
  els.messages.append(node); node.querySelector(".message-body").innerHTML=markdown(content); scrollToLatest("smooth"); return node;
}
function setBusy(value){state.busy=value;els.send.disabled=value;els.prompt.disabled=value;}
function formatSeconds(ms){return ms<1000?`${Math.round(ms)} ms`:`${(ms/1000).toFixed(2)} s`;}

async function checkHealth(){
  els.badge.className="status checking";els.badge.querySelector("span").textContent="Checking…";
  const started=performance.now();
  try{const response=await fetch("/api/status");const data=await response.json();els.badge.className=`status ${data.healthy?"healthy":"error"}`;els.badge.querySelector("span").textContent=data.healthy?`Healthy · ${formatSeconds(data.latencyMs)}`:"Unavailable";return data.healthy;}
  catch{els.badge.className="status error";els.badge.querySelector("span").textContent=`Unavailable · ${formatSeconds(performance.now()-started)}`;return false;}
}

function updateMetrics({started,firstToken,finished,usage,kind}){
  const ttft=firstToken-started,total=finished-started,generation=Math.max(1,finished-firstToken),completion=usage.completion_tokens||0;
  els.metrics.classList.add("visible");els.ttft.textContent=formatSeconds(ttft);els.total.textContent=formatSeconds(total);els.tokens.textContent=completion?`${completion} out · ${usage.prompt_tokens||0} in`:"n/a";els.tps.textContent=completion?`${(completion/(generation/1000)).toFixed(1)} tok/s`:"n/a";els.kind.textContent=kind;els.fill.style.width=`${Math.min(100,(ttft/total)*100)}%`;els.note.textContent=`TTFT is ${Math.round(ttft/total*100)}% of total latency. Throughput excludes time to first token.`;
}

async function run(prompt,kind="chat"){
  if(state.busy||!prompt.trim())return;
  const history=[...state.messages,{role:"user",content:prompt.trim()}];state.messages=history;addMessage("user",prompt.trim());els.prompt.value="";els.prompt.style.height="auto";setBusy(true);
  const assistant=addMessage("assistant","");const body=assistant.querySelector(".message-body");body.classList.add("cursor");if(state.webSearch)body.innerHTML='<div class="searching">Searching the web…</div>';
  const started=performance.now();let firstToken=0,content="",reasoning="",usage={},sources=[],searchMs=0;
  try{
    const response=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:history.slice(-2),max_tokens:Number($("#maxTokens").value),temperature:Number($("#temperature").value),enable_thinking:$("#thinking").checked,web_search:state.webSearch})});
    if(!response.ok){const e=await response.json().catch(()=>({}));throw new Error(e.error||`Request failed (${response.status})`);}
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="";
    while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split("\n");buffer=lines.pop()||"";
      for(const line of lines){if(!line.startsWith("data: "))continue;const data=line.slice(6).trim();if(!data||data==="[DONE]")continue;const chunk=JSON.parse(data);if(chunk.sources){sources=chunk.sources;searchMs=chunk.search_ms||0;continue}if(chunk.usage)usage=chunk.usage;for(const choice of chunk.choices||[]){const d=choice.delta||{};const next=d.content||"",thought=d.reasoning||d.reasoning_content||"";if((next||thought)&&!firstToken)firstToken=performance.now();content+=next;reasoning+=thought;}body.innerHTML=`${reasoning?`<div class="thinking-block">${markdown(reasoning)}</div>`:""}${markdown(content)}`;scrollToLatest();}
    }
    if(!firstToken)throw new Error("The stream ended without generated text");const finished=performance.now();if(sources.length)body.insertAdjacentHTML("beforeend",`<div class="sources"><strong>Sources${searchMs?` · ${(searchMs/1000).toFixed(1)}s`:""}</strong><div class="source-list">${sources.map(source=>`<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer" title="${escapeHtml(source.title)}">${source.id}. ${escapeHtml(source.title)}</a>`).join("")}</div></div>`);state.messages.push({role:"assistant",content});state.lastCompletedAt=Date.now();localStorage.setItem("lastCompletedAt",String(state.lastCompletedAt));updateMetrics({started,firstToken,finished,usage,kind:state.webSearch?"web search":kind});if(searchMs)els.note.textContent+=` Web search took ${(searchMs/1000).toFixed(2)}s and is included in TTFT.`;els.badge.className="status healthy";els.badge.querySelector("span").textContent="Healthy";
  }catch(error){body.innerHTML=`<p><strong>Request failed.</strong> ${escapeHtml(error.message)}</p>`;els.badge.className="status error";els.badge.querySelector("span").textContent="Request failed";}
  finally{body.classList.remove("cursor");setBusy(false);scrollToLatest("smooth");els.prompt.focus();}
}

const benchmarkPrompt="Reply with a concise explanation of why streaming improves perceived LLM latency. Use exactly three bullet points.";
$("#healthButton").addEventListener("click",checkHealth);
$("#webSearchButton").addEventListener("click",()=>{state.webSearch=!state.webSearch;const button=$("#webSearchButton");button.classList.toggle("active",state.webSearch);button.setAttribute("aria-pressed",String(state.webSearch));button.title=state.webSearch?"Web Search enabled":"Ground the answer with Tavily web results";});
$("#warmButton").addEventListener("click",()=>run(benchmarkPrompt,"warm test"));
$("#coldButton").addEventListener("click",()=>{const idle=(Date.now()-state.lastCompletedAt)/1000;if(state.lastCompletedAt&&idle<300&&!confirm(`Only ${Math.round(idle)} seconds have passed since the last request. The configured scale-down delay is 300 seconds, so this will probably be warm. Run anyway?`))return;run(benchmarkPrompt,"cold candidate")});
els.send.addEventListener("click",()=>run(els.prompt.value));els.prompt.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();run(els.prompt.value)}});els.prompt.addEventListener("input",()=>{els.prompt.style.height="auto";els.prompt.style.height=`${els.prompt.scrollHeight}px`});
document.querySelectorAll("[data-prompt]").forEach(b=>b.addEventListener("click",()=>{els.prompt.value=b.dataset.prompt;els.prompt.dispatchEvent(new Event("input"));els.prompt.focus()}));
$("#settingsButton").addEventListener("click",()=>$("#settingsDialog").showModal());
for(const id of ["maxTokens","temperature"]){const input=$("#"+id),output=$("#"+id+"Value");input.addEventListener("input",()=>output.textContent=input.value)}
fetch("/api/config").then(r=>r.json()).then(config=>{state.config=config;$("#modelName").textContent=config.model;$("#webSearchButton").classList.toggle("configured",config.webSearchConfigured);if(!config.webSearchConfigured)$("#webSearchButton").title="Add TAVILY_API_KEY to .env to enable Web Search";if(!config.configured){els.badge.className="status error";els.badge.querySelector("span").textContent="API key missing";}});
