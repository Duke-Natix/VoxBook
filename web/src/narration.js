const ROMAN = /^[IVXLCDM]+$/;
const ROMAN_VALUES = {I:1,V:5,X:10,L:50,C:100,D:500,M:1000};
const ACRONYMS = new Set([
  'AI','KI','TTS','PDF','APK','CPU','GPU','USB','SSD','HDD','RAM','ROM','ONNX','API','URL','URI','HTTP','HTTPS','HTML','CSS','JS','JSON','XML',
  'GPS','WLAN','WIFI','TV','PC','VR','AR','EU','USA','UK','UNO','NATO','FBI','CIA','DNA','RNA','ISBN','UHD','HD','LED','LCD','OLED','GTA','RPG','MMO','NPC'
]);

function romanToInt(value){
  const s=String(value||'').toUpperCase();
  if(!ROMAN.test(s)) return null;
  let total=0,prev=0;
  for(let i=s.length-1;i>=0;i--){
    const n=ROMAN_VALUES[s[i]]||0;
    if(n<prev) total-=n; else {total+=n;prev=n;}
  }
  return total>=1&&total<=3999?total:null;
}

function titleCaseWord(word,language){
  const locale=language==='de'?'de-DE':'en-US';
  const lower=word.toLocaleLowerCase(locale);
  return lower.charAt(0).toLocaleUpperCase(locale)+lower.slice(1);
}

function normalizeAllCaps(text,language){
  return String(text||'').replace(/\b[\p{Lu}ÄÖÜẞ][\p{Lu}ÄÖÜẞ]{2,}\b/gu,word=>{
    const upper=word.toLocaleUpperCase(language==='de'?'de-DE':'en-US');
    if(ACRONYMS.has(upper)||ROMAN.test(upper)) return word;
    return titleCaseWord(word,language);
  });
}

function expandCommon(text,language){
  let s=text;
  const pairs=language==='de' ? [
    [/\bz\.\s*B\./gi,'zum Beispiel'],[/\bbzw\./gi,'beziehungsweise'],[/\bd\.\s*h\./gi,'das heißt'],[/\bu\.\s*a\./gi,'unter anderem'],[/\bca\./gi,'circa'],[/\busw\./gi,'und so weiter'],[/\bDr\./g,'Doktor'],[/\bNr\./gi,'Nummer']
  ] : [
    [/\be\.\s*g\./gi,'for example'],[/\bi\.\s*e\./gi,'that is'],[/\bMr\./g,'Mister'],[/\bMrs\./g,'Misses'],[/\bDr\./g,'Doctor'],[/\bNo\./g,'Number']
  ];
  for(const [re,to] of pairs) s=s.replace(re,to);
  return s.replace(/\s*&\s*/g,language==='de'?' und ':' and ');
}

function replaceRomans(text,language){
  const chapterWord=language==='de'?'Kapitel':'Chapter';
  let s=text;
  const heading=/^(?:(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section)\s+)?([IVXLCDM]+)\.?$/i;
  s=s.split('\n').map(line=>{
    const t=line.trim(),m=t.match(heading);
    if(!m) return line;
    const n=romanToInt(m[2]);
    if(!n) return line;
    if(m[1]) return `${m[1]} ${n}.`;
    if(language==='en'&&m[2].toUpperCase()==='I') return `${chapterWord} 1.`;
    return `${chapterWord} ${n}.`;
  }).join('\n');
  s=s.replace(/\b(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section)\s+([IVXLCDM]+)\b/gi,(all,prefix,r)=>{
    const n=romanToInt(r);return n?`${prefix} ${n}`:all;
  });
  return s;
}

function looksHeading(block){
  const t=String(block||'').trim();
  if(!t||t.length>100||/[!?]$/.test(t)) return false;
  if(/^(Kapitel|Chapter|Teil|Part|Band|Book|Akt|Act|Abschnitt|Section|Inhalt|Contents|Prolog|Prologue|Epilog|Epilogue)\b/i.test(t)) return true;
  const words=t.split(/\s+/);
  return words.length<=7&&!/[.!?]$/.test(t)&&(/^[\p{Lu}\d\s:,'’"„“\-–—]+$/u.test(t)||words.length<=2);
}

function normalizeListPrefix(line){
  let s=line.trim();
  let m=s.match(/^([IVXLCDM]+)[.)]\s+(.+)$/i);
  if(m){const n=romanToInt(m[1]);if(n)s=`${n}. ${m[2]}`;return {text:s,isList:true};}
  m=s.match(/^(\d{1,3})[.)]\s+(.+)$/);
  if(m) return {text:`${m[1]}. ${m[2]}`,isList:true};
  m=s.match(/^[•●▪◦‣⁃*+-]\s+(.+)$/);
  if(m) return {text:m[1],isList:true};
  return {text:s,isList:false};
}

export function prepareNarrationText(raw,language='de'){
  let s=String(raw||'')
    .replace(/\u00ad/g,'')
    .replace(/[\u200B-\u200D\uFEFF]/g,'')
    .replace(/\u00a0/g,' ')
    .replace(/\r\n?/g,'\n');

  // Only reconnect real word-wrap hyphenation. List dashes and intentional
  // compounds remain untouched.
  s=s.replace(/([\p{L}])[-‐‑]\s*\n\s*([\p{Ll}äöüß])/gu,'$1$2');

  const rawLines=s.split('\n');
  const blocks=[];
  let paragraph=[];
  const flush=()=>{
    if(!paragraph.length) return;
    const text=paragraph.join(' ').replace(/[ \t]{2,}/g,' ').trim();
    if(text) blocks.push(text);
    paragraph=[];
  };

  for(const sourceLine of rawLines){
    let line=sourceLine.replace(/[ \t]+/g,' ').trim();
    if(!line){flush();continue;}
    if(/^(?:Seite|Page)\s+\d+(?:\s+(?:von|of)\s+\d+)?\s*$/i.test(line)) continue;
    if(/^\d{1,4}$/.test(line)) continue;
    if(/^(?:[-–—_=*#•·.]{2,}|[.·•])$/.test(line)) continue;

    line=line.replace(/\.{3,}|…/g,', ')
             .replace(/([!?])\1{1,}/g,'$1')
             .replace(/\s+([,.;:!?])/g,'$1')
             .replace(/([,;:])(?=\S)/g,'$1 ');
    line=normalizeAllCaps(line,language);

    const list=normalizeListPrefix(line);
    line=list.text;
    if(looksHeading(line)||list.isList){
      flush();
      blocks.push(line);
      continue;
    }
    paragraph.push(line);
  }
  flush();

  s=blocks.join('\n\n');
  s=replaceRomans(s,language);
  s=normalizeAllCaps(s,language);
  s=expandCommon(s,language);
  return s.replace(/(^|\s)[.·•](?=\s|$)/g,' ')
          .replace(/,\s*,+/g,',')
          .replace(/\.{2,}/g,'.')
          .replace(/[ \t]{2,}/g,' ')
          .replace(/ *\n */g,'\n')
          .replace(/\n{3,}/g,'\n\n')
          .trim();
}

function splitSentences(text,language){
  if(typeof Intl!=='undefined'&&Intl.Segmenter){
    try{
      const seg=new Intl.Segmenter(language==='de'?'de-DE':'en-US',{granularity:'sentence'});
      return Array.from(seg.segment(text),x=>x.segment.trim()).filter(Boolean);
    }catch{}
  }
  return (text.match(/[^.!?]+(?:[.!?]+[”"'’]?|$)/g)||[text]).map(x=>x.trim()).filter(Boolean);
}

function splitLongSentence(sentence,language,max=190,min=75){
  const out=[];
  let rest=sentence.trim();
  const conjunctions=language==='de' ? [' und ',' aber ',' denn ',' weil ',' während ',' obwohl ',' damit ',' wenn ',' als '] : [' and ',' but ',' because ',' while ',' although ',' so that ',' when ',' as '];
  while(rest.length>max){
    let cut=-1;
    const window=rest.slice(0,max+1);
    for(let i=Math.min(max,window.length-1);i>=min;i--){
      if(/[,:;–—]/.test(window[i])){cut=i+1;break;}
    }
    if(cut<0){
      let best=-1;
      for(const c of conjunctions){
        const i=window.lastIndexOf(c);
        if(i>=min&&i>best) best=i;
      }
      if(best>=min) cut=best;
    }
    if(cut<0){
      const i=window.lastIndexOf(' ');
      cut=i>=min?i:max;
    }
    let part=rest.slice(0,cut).trim();
    rest=rest.slice(cut).trim();
    if(part&&!/[,.!?;:]$/.test(part)) part+=',';
    if(part) out.push(part);
  }
  if(rest) out.push(rest);
  return out;
}

function narratorSentence(sentence){
  let s=sentence.trim()
    .replace(/\s*;\s*/g,'; ')
    .replace(/\s*:\s*/g,': ')
    .replace(/\s+([,.;:!?])/g,'$1');
  if(!/[.!?;,]$/.test(s)&&s.length<190) s+='.';
  return s;
}

function isListBlock(block){return /^(?:\d{1,3}[.)]\s+|[IVXLCDM]+[.)]\s+|[•●▪◦‣⁃*+-]\s+)/i.test(block.trim());}

export function buildNarrationSegments(raw,language='de',options={}){
  const clean=prepareNarrationText(raw,language);
  if(!clean) return [];
  const blocks=clean.split(/\n\s*\n+/).map(x=>x.trim()).filter(Boolean);
  const out=[];

  for(const block0 of blocks){
    const block=block0.replace(/[ \t]+/g,' ').trim();
    if(!block) continue;

    if(looksHeading(block)){
      out.push(/[.!?]$/.test(block)?block:block+'.');
      continue;
    }

    if(isListBlock(block)){
      const listText=narratorSentence(block);
      for(const part of splitLongSentence(listText,language,175,60)) out.push(narratorSentence(part));
      continue;
    }

    const sentences=splitSentences(block,language);
    let current='';
    const flush=()=>{if(current.trim()){out.push(current.trim());current='';}};
    for(const sentence0 of sentences){
      for(const piece0 of splitLongSentence(sentence0,language,190,75)){
        const piece=narratorSentence(piece0);
        if(!piece) continue;
        if(current&&current.length+piece.length+1>215) flush();
        current+=(current?' ':'')+piece;
        if(current.length>=130||/[!?]$/.test(piece)) flush();
      }
    }
    flush();
  }

  return out.filter(Boolean);
}
