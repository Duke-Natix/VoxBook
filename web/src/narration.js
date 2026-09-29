const ROMAN = /^[IVXLCDM]+$/;
const ROMAN_VALUES = {I:1,V:5,X:10,L:50,C:100,D:500,M:1000};

function romanToInt(value){
  const s=String(value||'').toUpperCase();
  if(!ROMAN.test(s)) return null;
  let total=0, prev=0;
  for(let i=s.length-1;i>=0;i--){
    const n=ROMAN_VALUES[s[i]]||0;
    if(n<prev) total-=n; else { total+=n; prev=n; }
  }
  if(total<1 || total>3999) return null;
  return total;
}

function expandCommon(text, language){
  let s=text;
  const pairs = language==='de' ? [
    [/\bz\.\s*B\./gi,'zum Beispiel'],[/\bbzw\./gi,'beziehungsweise'],[/\bd\.\s*h\./gi,'das heißt'],[/\bu\.\s*a\./gi,'unter anderem'],[/\bca\./gi,'circa'],[/\busw\./gi,'und so weiter'],[/\bDr\./g,'Doktor'],[/\bNr\./gi,'Nummer']
  ] : [
    [/\be\.\s*g\./gi,'for example'],[/\bi\.\s*e\./gi,'that is'],[/\bMr\./g,'Mister'],[/\bMrs\./g,'Misses'],[/\bDr\./g,'Doctor'],[/\bNo\./g,'Number']
  ];
  for(const [re,to] of pairs) s=s.replace(re,to);
  s=s.replace(/\s*&\s*/g, language==='de'?' und ':' and ');
  return s;
}

function replaceRomans(text, language){
  const chapterWord=language==='de'?'Kapitel':'Chapter';
  let s=text;
  const heading = /^(?:(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section)\s+)?([IVXLCDM]+)\.?$/i;
  s=s.split('\n').map(line=>{
    const t=line.trim();
    const m=t.match(heading);
    if(!m) return line;
    const upper=m[2].toUpperCase();
    const n=romanToInt(upper);
    if(!n) return line;
    if(m[1]) return `${m[1]} ${n}.`;
    if(language==='en' && upper==='I') return `${chapterWord} 1.`;
    return `${chapterWord} ${n}.`;
  }).join('\n');
  s=s.replace(/\b(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section)\s+([IVXLCDM]+)\b/gi,(all,prefix,r)=>{
    const n=romanToInt(r); return n?`${prefix} ${n}`:all;
  });
  s=s.replace(/\b(II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX|XXI|XXII|XXIII|XXIV|XXV|XXX|XL|L|LX|LXX|LXXX|XC|C)\b/g,r=>String(romanToInt(r)||r));
  if(language==='de') s=s.replace(/(^|[\s(\[])(I)(?=[\s).,:;!?\]])/g,(m,p)=>p+'1');
  return s;
}

export function prepareNarrationText(raw, language='de'){
  let s=String(raw||'')
    .replace(/\u00ad/g,'')
    .replace(/[\u200B-\u200D\uFEFF]/g,'')
    .replace(/\u00a0/g,' ')
    .replace(/\r\n?/g,'\n');

  // Reconnect words that PDFs split only because of a line break.
  s=s.replace(/([\p{L}])[-‐‑]\s*\n\s*([\p{Ll}äöüß])/gu,'$1$2');

  const lines=s.split('\n');
  const cleaned=[];
  for(let rawLine of lines){
    let line=rawLine.trim();
    if(!line){ cleaned.push(''); continue; }
    if(/^(?:Seite|Page)\s+\d+(?:\s+(?:von|of)\s+\d+)?\s*$/i.test(line)) continue;
    if(/^(?:[-–—_=*#•·.]{2,}|[.·•])$/.test(line)) continue;
    line=line.replace(/^[\s>*•●▪◦‣⁃]+/,'');
    line=line.replace(/^([IVXLCDM]+)[.)]\s+/,(m,r)=>{const n=romanToInt(r);return n?`${n}. `:m});
    line=line.replace(/^[-–—]\s+(?=\p{L}|["„“'‘’])/u,'');
    line=line.replace(/\s+[-–—]\s+/g,', ');
    line=line.replace(/\.{3,}|…/g,', ');
    line=line.replace(/([!?])\1{1,}/g,'$1');
    line=line.replace(/\s+([,.;:!?])/g,'$1');
    line=line.replace(/([,;:])(?=\S)/g,'$1 ');
    cleaned.push(line);
  }
  s=cleaned.join('\n').replace(/\n{3,}/g,'\n\n');
  s=replaceRomans(s,language);
  s=expandCommon(s,language);
  s=s.replace(/(^|\s)[.·•](?=\s|$)/g,' ')
     .replace(/,\s*,+/g,',')
     .replace(/\.{2,}/g,'.')
     .replace(/[ \t]{2,}/g,' ')
     .replace(/ *\n */g,'\n')
     .replace(/\n{3,}/g,'\n\n')
     .trim();
  return s;
}

function splitSentences(text){
  if(typeof Intl!=='undefined' && Intl.Segmenter){
    try{
      const seg=new Intl.Segmenter(undefined,{granularity:'sentence'});
      return Array.from(seg.segment(text),x=>x.segment.trim()).filter(Boolean);
    }catch{}
  }
  return (text.match(/[^.!?]+(?:[.!?]+[”"'’]?|$)/g)||[text]).map(x=>x.trim()).filter(Boolean);
}

function looksHeading(block){
  const t=block.trim();
  if(!t || t.length>90 || /[!?]$/.test(t)) return false;
  if(/^(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section)\b/i.test(t)) return true;
  const words=t.split(/\s+/);
  if(words.length<=8 && !/[.!?]$/.test(t) && (/^[\p{Lu}\d\s:,'’"„“\-–—]+$/u.test(t) || words.length<=3)) return true;
  return false;
}

export function buildNarrationSegments(raw, language='de', options={}){
  const clean=prepareNarrationText(raw,language);
  if(!clean) return [];
  const blocks=clean.split(/\n\s*\n+/).map(x=>x.replace(/\s*\n\s*/g,' ').trim()).filter(Boolean);
  const out=[];
  let current='';
  let pendingHeading='';
  const target=900, max=1200, min=340;
  const flush=()=>{ if(current.trim()){out.push(current.trim());current='';} };

  for(const block0 of blocks){
    let block=block0;
    if(looksHeading(block)){
      if(current.length>=min) flush();
      pendingHeading=/[.!?]$/.test(block)?block:block+'.';
      continue;
    }
    if(pendingHeading){ block=pendingHeading+' '+block; pendingHeading=''; }
    const sentences=splitSentences(block);
    for(const sentence0 of sentences){
      let sentence=sentence0.trim();
      if(!sentence) continue;
      if(!/[.!?]$/.test(sentence) && sentence.length<180) sentence+='.';
      if(current && current.length+sentence.length+1>max) flush();
      current+=(current?' ':'')+sentence;
      const dialogueStart=/^[„“"'‘’]/.test(sentence);
      if(current.length>=target && (!options.dialogueMode || !dialogueStart)) flush();
    }
  }
  if(pendingHeading) current+=(current?' ':'')+pendingHeading;
  flush();

  // Tiny fragments cause audible stop/start edges, so merge the last one when safe.
  if(out.length>1 && out[out.length-1].length<min){
    const last=out.pop();
    if(out[out.length-1].length+last.length+1<=max*1.25) out[out.length-1]+=' '+last;
    else out.push(last);
  }
  return out;
}
