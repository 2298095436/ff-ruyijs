// CSS Backgrounds 3: expand once in the declaration store, before the cascade.
#include "domain/styling/css_background_value.h"
#include "domain/styling/css_components.h"
#include "domain/styling/css_color_value.h"
#include "domain/styling/css_numeric_value.h"
#include "domain/styling/css_specified_value.h"
#include "domain/styling/css_float_text.h"
#include "domain/browser_environment/url_value.h"
#include <algorithm>
#include <array>

namespace ruyijs::domain::styling {
namespace background_value {
constexpr const char* names[] = {"background-image", "background-position-x", "background-position-y",
  "background-size", "background-repeat", "background-attachment", "background-origin",
  "background-clip", "background-color"};
constexpr const char* initial[] = {"none", "0%", "0%", "auto", "repeat", "scroll",
  "padding-box", "border-box", "rgba(0, 0, 0, 0)"};
bool Word(const std::string& value, const char* words) {
  for (const auto& word : CssSplit(words, ',')) if (value == word) return true;
  return false;
}
bool Wide(const std::string& v) { return Word(v,"initial,inherit,unset,revert,revert-layer"); }
std::vector<std::string> Tokens(const std::string&);
bool Position(const std::vector<std::string>&,std::string*,std::string*);
std::string Clean(const std::string& input) {
  std::string out;
  for (size_t i=0;i<input.size();) {
    const auto start=i;
    if (input[i]=='\\') { out+=input[i++]; if(i<input.size()) out+=input[i++]; }
    else if (input[i]=='\'' || input[i]=='"') {
      const auto quote=input[i++];
      while (i<input.size()) { if (input[i]=='\\' && i+1<input.size()) {i+=2;continue;} if(input[i++]==quote) break; }
      out+=input.substr(start,i-start);
    } else if (CssLower(input.substr(i,4))=="url(") {
      const auto end=CssClosing(input,i+3);
      if (end==input.size()) return {};
      out+=input.substr(i,end-i+1);i=end+1;
    } else if (input.compare(i,2,"/*")==0) { i=CssSkip(input,i);out+=' '; }
    else out+=input[i++];
  }
  return CssTrim(out);
}
bool Image(const std::string& value) {
  const auto lower = CssLower(value);
  if (lower == "none") return true;
  const auto open = value.find('(');
  if (open == value.npos || CssClosing(value, open) != value.size()-1) return false;
  const auto kind=lower.substr(0,open),body=CssTrim(value.substr(open+1,value.size()-open-2));
  if (kind=="url") {
    if (body.empty()) return true;
    if (body[0]=='\'' || body[0]=='"') {
      size_t i=1;
      while (i<body.size() && body[i]!=body[0]) {if(body[i]=='\\') ++i; ++i;}
      return i+1==body.size();
    }
    for (size_t i=0;i<body.size();++i) {
      if (body[i]=='\\') { if (++i==body.size()) return false; continue; }
      if (CssSpace(body[i]) || body[i]=='\'' || body[i]=='"' || body[i]=='(' || body[i]==')' ||
          static_cast<unsigned char>(body[i])<32) return false;
    }
    return true;
  }
  if (kind=="-moz-element") return body.size()>1 && body[0]=='#' && Tokens(body).size()==1;
  if (kind=="image-set" || kind=="-webkit-image-set") {
    if (body.empty()) return false;
    for (const auto& choice:CssSplit(body,',')) {
      const auto words=Tokens(choice);
      if (words.empty() || words.size()>3) return false;
      if (!Image(words[0]) && !(words[0].size()>1 && (words[0][0]=='"' || words[0][0]=='\''))) return false;
      bool density=false,type=false;
      for (size_t i=1;i<words.size();++i) {
        const auto v=CssLower(words[i]);
        if (v.starts_with("type(")) {if(type) return false;type=true;}
        else {
          const auto number=CssNumericParse(v);
          if (density || number.kind!=CssResolution || number.number<0) return false;
          density=true;
        }
      }
    }
    return true;
  }
  if (!Word(kind,"linear-gradient,radial-gradient,repeating-linear-gradient,repeating-radial-gradient,conic-gradient,repeating-conic-gradient")) return false;
  const bool conic=kind.find("conic")!=kind.npos,radial=kind.find("radial")!=kind.npos;
  const auto groups=CssSplit(body,',');
  size_t first=0;
  if (!groups.empty()) {
    const auto words=Tokens(CssLower(groups[0]));
    if (words.empty()) return false;
    if (!CssColorSupported(words[0])) {
      bool header=false;
      if (!conic && !radial) {
        if (words.size()==1) header=CssNumericAllowed(words[0],CssAngle);
        else if (words[0]=="to" && words.size()<=3) {
          bool x=false,y=false;header=true;
          for (size_t i=1;i<words.size();++i) {
            if (Word(words[i],"left,right")) { if(x) header=false; x=true; }
            else if (Word(words[i],"top,bottom")) { if(y) header=false;y=true; }
            else header=false;
          }
        }
      } else {
        // The optional radial/conic header precedes the first colour stop.
        size_t at=0;
        if (conic && words[at]=="from" && words.size()>1) {
          if (!CssNumericAllowed(words[1],CssAngle)) return false;at=2;header=true;
        }
        while (radial && at<words.size() && words[at]!="at") {
          if (!Word(words[at],"circle,ellipse,closest-side,closest-corner,farthest-side,farthest-corner") &&
              !CssNumericAllowed(words[at],CssLength|CssPercent,false)) return false;
          header=true;++at;
        }
        if (at<words.size() && words[at]=="at") {
          std::string x,y;
          header=Position(std::vector<std::string>(words.begin()+at+1,words.end()),&x,&y);
          at=words.size();
        }
        header=header && at==words.size();
      }
      if (!header) return false;
      first=1;
    }
  }
  size_t colors=0;
  for (size_t i=first;i<groups.size();++i) {
    auto words=Tokens(CssLower(groups[i]));
    if (words.empty()) return false;
    const bool color=CssColorSupported(words[0]);
    if (color) ++colors;
    else if (i==first || i+1==groups.size()) return false;
    if (words.size()>(color?3u:1u)) return false;
    for (size_t j=color?1:0;j<words.size();++j)
      if (!CssNumericAllowed(words[j],(conic?CssAngle:CssLength)|CssPercent)) return false;
  }
  return colors>0;
}
std::vector<std::string> Tokens(const std::string& text) {
  std::vector<std::string> result;
  for (size_t p=0; p<text.size();) {
    p=CssSkip(text,p); if (p==text.size()) break;
    if (text[p]=='/') { result.push_back("/"); ++p; continue; }
    const auto end=CssDelimiter(text,p," \t\r\n\f/");
    if (end==p) return {};
    result.push_back(text.substr(p,end-p)); p=end;
  }
  return result;
}
bool PositionWord(const std::string& v) {
  return Word(CssLower(v),"left,right,top,bottom,center") || CssNumericAllowed(v,CssLength|CssPercent);
}
bool Horizontal(const std::string& v) { return v=="left" || v=="right"; }
bool Vertical(const std::string& v) { return v=="top" || v=="bottom"; }
bool Position(const std::vector<std::string>& words, std::string* x, std::string* y) {
  if (words.empty() || words.size()>4) return false;
  for (const auto& word:words) if (!PositionWord(word)) return false;
  *x=*y="center";
  if (words.size()==1) {
    (Vertical(words[0])?*y:*x)=words[0]; return true;
  }
  if (words.size()==2) {
    *x=words[0]; *y=words[1];
    if (Vertical(*x)) {
      if (!Horizontal(*y) && *y!="center") return false;
      std::swap(*x,*y);
    } else if (Horizontal(*y)) {
      if (*x!="center") return false;
      std::swap(*x,*y);
    }
    return !Vertical(*x) && !Horizontal(*y);
  }
  bool seenX=false,seenY=false,center=false;
  for (size_t i=0;i<words.size();++i) {
    const auto& word=words[i];
    if (word=="center") {
      if (center) return false;
      center=true;
      continue;
    }
    const bool horizontal=Horizontal(word),vertical=Vertical(word);
    if ((!horizontal&&!vertical) || (horizontal?seenX:seenY)) return false;
    std::string axis=word;
    if (i+1<words.size() && CssNumericAllowed(words[i+1],CssLength|CssPercent)) axis+=" "+words[++i];
    (horizontal?*x:*y)=axis; (horizontal?seenX:seenY)=true;
  }
  if (center) {
    if (seenX==seenY) return false;
    if (!seenX) { *x="center"; seenX=true; }
    else { *y="center"; seenY=true; }
  }
  return seenX&&seenY;
}
bool SizeWord(const std::string& v) {
  return v=="auto" || CssNumericAllowed(v,CssLength|CssPercent,false);
}
bool Reference(const std::string& text) {
  for (size_t p=0;p<text.size();++p) {
    if (text[p]=='\\') { ++p; continue; }
    if (text[p]=='\'' || text[p]=='"') {
      const char quote=text[p++];
      for (;p<text.size() && text[p]!=quote;++p) if (text[p]=='\\') ++p;
      continue;
    }
    if ((p==0 || !((text[p-1]>='a'&&text[p-1]<='z') || text[p-1]=='-')) &&
        (CssLower(text.substr(p,4))=="var(" || CssLower(text.substr(p,4))=="env(")) return true;
  }
  return false;
}
bool Layer(const std::string& input, bool last, std::array<std::string,9>* result) {
  auto words=Tokens(input); if (words.empty()) return false;
  for (size_t i=0;i<9;++i) (*result)[i]=initial[i];
  std::vector<std::string> position,repeats,boxes;
  bool image=false,attachment=false,color=false,slash=false,positionSeen=false;
  for (size_t i=0;i<words.size();++i) {
    const auto lower=CssLower(words[i]);
    if (Wide(lower)) return false;
    if (lower=="/") {
      if (slash || position.empty() || i==0 || !PositionWord(CssLower(words[i-1])) || ++i==words.size()) return false;
      slash=true;
      const auto first=CssLower(words[i]);
      if (first=="cover" || first=="contain") (*result)[3]=first;
      else {
        if (!SizeWord(first)) return false;
        (*result)[3]=CssSpecifiedValue("background-size",first);
        const auto second=i+1<words.size() && SizeWord(CssLower(words[i+1]))
            ?CssSpecifiedValue("background-size",words[++i]):std::string("auto");
        if (first!="auto" || second!="auto") (*result)[3]+=" "+second;
      }
    } else if (Image(words[i])) {
      if (image) return false;
      image=true; (*result)[0]=CssSpecifiedValue("background-image",words[i]);
    } else if (Word(lower,"repeat,no-repeat,space,round,repeat-x,repeat-y")) {
      if (repeats.size()==2) return false;
      repeats.push_back(lower);
    } else if (Word(lower,"scroll,fixed,local")) {
      if (attachment) return false;
      attachment=true; (*result)[5]=lower;
    } else if (Word(lower,"border-box,padding-box,content-box")) {
      if (boxes.size()==2) return false;
      boxes.push_back(lower);
    } else if (PositionWord(lower)) {
      if (slash || positionSeen) return false;
      positionSeen=true;
      do {
        if (position.size()==4) return false;
        position.push_back(CssSpecifiedValue("background-position",CssLower(words[i])));
      } while (i+1<words.size() && PositionWord(CssLower(words[i+1])) && ++i);
    } else if (last && !color && CssColorSupported(lower)) {
      color=true; (*result)[8]=CssSpecifiedValue("background-color",words[i]);
    } else return false;
  }
  if (!position.empty() && !Position(position,&(*result)[1],&(*result)[2])) return false;
  if (!repeats.empty()) {
    if (repeats.size()==2 && (Word(repeats[0],"repeat-x,repeat-y") || Word(repeats[1],"repeat-x,repeat-y"))) return false;
    (*result)[4]=repeats[0];
    if (repeats.size()==2 && repeats[1]!=repeats[0]) {
      if (repeats[0]=="repeat" && repeats[1]=="no-repeat") (*result)[4]="repeat-x";
      else if (repeats[0]=="no-repeat" && repeats[1]=="repeat") (*result)[4]="repeat-y";
      else (*result)[4]+=" "+repeats[1];
    }
  }
  if (!boxes.empty()) { (*result)[6]=boxes[0]; (*result)[7]=boxes.back(); }
  return true;
}
}  // namespace background_value

std::vector<std::string> CssBackgroundLonghands() {
  return {std::begin(background_value::names),std::end(background_value::names)};
}
bool CssBackgroundImage(const std::string& input) {
  if (!CssValueComponentsValid(input)) return false;
  const auto layers=CssSplit(background_value::Clean(input),',');
  return !layers.empty() && std::all_of(layers.begin(),layers.end(),background_value::Image);
}
std::string CssBackgroundResolveURLs(const std::string& input,const std::string& base) {
  std::string result;
  for (size_t i=0;i<input.size();) {
    if (CssLower(input.substr(i,4))!="url(") {
      if(input[i]=='"' || input[i]=='\'') {
        const auto quote=input[i];result+=input[i++];
        while(i<input.size()) { const auto c=input[i++];result+=c;
          if(c=='\\' && i<input.size()) result+=input[i++];else if(c==quote) break; }
      } else result+=input[i++];
      continue;
    }
    const auto end=CssClosing(input,i+3);
    if(end==input.size()) return input;
    auto body=CssTrim(input.substr(i+4,end-i-4));
    if(body.size()>=2 && (body[0]=='"'||body[0]=='\'')) body=body.substr(1,body.size()-2);
    std::string decoded;
    for(size_t j=0;j<body.size();++j) {
      if(body[j]!='\\') {decoded+=body[j];continue;}
      if(++j==body.size()) break;
      unsigned code=0,count=0;
      const auto hex=[](char c)->int {return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:-1;};
      while(j<body.size()&&count<6&&hex(body[j])>=0) {code=code*16+hex(body[j++]);++count;}
      if(!count) {if(body[j]!='\n'&&body[j]!='\r') decoded+=body[j];continue;}
      if(j<body.size()&&CssSpace(body[j])) {if(body[j]=='\r'&&j+1<body.size()&&body[j+1]=='\n') ++j;}
      else --j;
      if(!code||code>0x10ffff||(code>=0xd800&&code<=0xdfff)) code=0xfffd;
      if(code<0x80) decoded+=char(code);
      else if(code<0x800) {decoded+=char(0xc0|(code>>6));decoded+=char(0x80|(code&63));}
      else if(code<0x10000) {decoded+=char(0xe0|(code>>12));decoded+=char(0x80|((code>>6)&63));decoded+=char(0x80|(code&63));}
      else {decoded+=char(0xf0|(code>>18));decoded+=char(0x80|((code>>12)&63));decoded+=char(0x80|((code>>6)&63));decoded+=char(0x80|(code&63));}
    }
    ruyijs::domain::browser_environment::UrlValue url;
    std::string resolved=decoded.empty()?std::string():
        ruyijs::domain::browser_environment::UrlValue::Resolve(decoded,base,&url)?url.href():"about:invalid";
    result+="url(\"";
    for(char c:resolved) {if(c=='"'||c=='\\') result+='\\';result+=c;}
    result+="\")";i=end+1;
  }
  return result;
}
std::string CssBackgroundSpecifiedImage(const std::string& input) {
  using namespace background_value;
  std::string result;
  for (const auto& part:CssSplit(input,',')) {
    std::string value=part;
    const auto open=value.find('(');
    if (open!=value.npos && Word(CssLower(value.substr(0,open)),"image-set,-webkit-image-set")) {
      std::string args;
      for (const auto& choice:CssSplit(value.substr(open+1,value.size()-open-2),',')) {
        auto words=Tokens(choice);
        const bool density=std::any_of(words.begin(),words.end(),[](const auto& word){
          return CssNumericParse(word).kind==CssResolution;
        });
        if (!density) words.insert(words.begin()+std::min(size_t(1),words.size()),"1x");
        if (!args.empty()) args+=", ";
        for (size_t i=0;i<words.size();++i) args+=(i?" ":"")+words[i];
      }
      value=part.substr(0,open+1)+args+")";
    }
    if (open!=value.npos && CssLower(value.substr(0,open)).find("gradient")!=std::string::npos) {
      auto groups=CssSplit(value.substr(open+1,value.size()-open-2),',');
      if (!groups.empty()) {
        auto words=Tokens(CssLower(groups[0]));
        const auto at=std::find(words.begin(),words.end(),"at");
        if (at!=words.end()) {
          std::string x,y;
          if (Position(std::vector<std::string>(at+1,words.end()),&x,&y) &&
              (x=="center" || x=="50%") && (y=="center" || y=="50%")) words.erase(at,words.end());
        }
        if (!words.empty() && !CssColorSupported(words[0])) {
          groups[0].clear();
          for (const auto& word:words) groups[0]+=(groups[0].empty()?"":" ")+word;
        } else if (words.empty()) groups.erase(groups.begin());
        value=part.substr(0,open+1);
        for (size_t i=0;i<groups.size();++i) value+=(i?", ":"")+groups[i];
        value+=")";
      }
    }
    if (!result.empty()) result+=", ";result+=value;
  }
  return result;
}
bool CssBackgroundLonghand(const std::string& name, const std::string& input) {
  using namespace background_value;
  if (!CssBackgroundProperty(name)) return false;
  if (!CssValueComponentsValid(input)) return false;
  const auto text=Clean(input), lower=CssLower(text);
  if (Wide(lower)) return true;
  if (Reference(text)) return CssVariableReferenceValid(input);
  if (name=="background-image") return CssBackgroundImage(text);
  if (name=="background-color") return CssColorSupported(lower);
  for (const auto& part:CssSplit(lower,',')) {
    auto words=Tokens(part);
    if (words.empty()) return false;
    if (name=="background-position-x" || name=="background-position-y") {
      const bool x=name.back()=='x';
      const auto axis=[&](const auto& v){return x?Horizontal(v):Vertical(v);};
      if (words.size()>2 || (words.size()==1 && !axis(words[0]) && words[0]!="center" &&
          !CssNumericAllowed(words[0],CssLength|CssPercent)) ||
          (words.size()==2 && (!axis(words[0]) || !CssNumericAllowed(words[1],CssLength|CssPercent)))) return false;
    } else if (name=="background-size") {
      if (words.size()==1 && Word(words[0],"cover,contain")) continue;
      if (words.size()>2 || !std::all_of(words.begin(),words.end(),SizeWord)) return false;
    } else if (name=="background-repeat") {
      if (words.size()==1 && Word(words[0],"repeat-x,repeat-y")) continue;
      if (words.size()>2 || !std::all_of(words.begin(),words.end(),[](const auto& v){return Word(v,"repeat,no-repeat,space,round");})) return false;
    } else if (words.size()!=1 || !Word(words[0],name=="background-attachment"?"scroll,fixed,local":
        name=="background-origin"?"border-box,padding-box,content-box":"border-box,padding-box,content-box,text")) return false;
  }
  return true;
}
bool CssBackgroundProperty(const std::string& name) {
  return std::find(std::begin(background_value::names),std::end(background_value::names),name)!=std::end(background_value::names);
}
bool CssBackgroundPositionExpand(const std::string& input, bool important, std::vector<CssDeclarationValue>* out) {
  using namespace background_value;
  if (!CssValueComponentsValid(input)) return false;
  const auto text=Clean(input),lower=CssLower(text);
  if (Wide(lower)) {
    *out={{"background-position-x",lower,important},{"background-position-y",lower,important}}; return true;
  }
  if (Reference(text)) {
    if (!CssVariableReferenceValid(input)) return false;
    *out={{"background-position",input,important}}; return true;
  }
  std::string x,y;
  for (const auto& part:CssSplit(lower,',')) {
    auto words=Tokens(part);
    for (auto& word:words) word=CssSpecifiedValue("background-position",word);
    std::string a,b;
    if (!Position(words,&a,&b)) return false;
    if (!x.empty()) { x+=", "; y+=", "; }
    x+=a; y+=b;
  }
  *out={{"background-position-x",x,important},{"background-position-y",y,important}}; return true;
}
std::string CssBackgroundPositionSerialize(const std::vector<CssDeclarationValue>& rows, bool* important) {
  if (important) *important=false;
  const auto x=std::find_if(rows.begin(),rows.end(),[](const auto& r){return r.name=="background-position-x";});
  const auto y=std::find_if(rows.begin(),rows.end(),[](const auto& r){return r.name=="background-position-y";});
  if (x==rows.end() || y==rows.end() || x->important!=y->important) {
    const auto p=std::find_if(rows.begin(),rows.end(),[](const auto& r){return r.name=="background-position";});
    if (p==rows.end() || x!=rows.end() || y!=rows.end()) return {};
    if (important) *important=p->important;
    return p->value;
  }
  if (important) *important=x->important;
  if (background_value::Wide(x->value) || background_value::Wide(y->value)) return x->value==y->value?x->value:std::string();
  const auto xs=CssSplit(x->value,','),ys=CssSplit(y->value,',');
  if (xs.size()!=ys.size()) return {};
  std::string result;
  for (size_t i=0;i<xs.size();++i) result+=(i?", ":"")+xs[i]+" "+ys[i];
  return result;
}
bool CssBackgroundExpand(const std::string& input, bool important, std::vector<CssDeclarationValue>* out) {
  using namespace background_value;
  if (!CssValueComponentsValid(input)) return false;
  const auto text=Clean(input),lower=CssLower(text);
  std::vector<CssDeclarationValue> rows;
  if (Wide(lower)) {
    for (const auto* name:names) rows.push_back({name,lower,important});
  } else if (Reference(text)) {
    if (!CssVariableReferenceValid(input)) return false;
    rows.push_back({"background",input,important});
  } else {
    const auto layers=CssSplit(text,',');
    std::array<std::string,9> values;
    for (size_t i=0;i<layers.size();++i) {
      std::array<std::string,9> layer;
      if (!Layer(layers[i],i+1==layers.size(),&layer)) return false;
      for (size_t n=0;n<8;++n) values[n]+=(i?", ":"")+layer[n];
      values[8]=layer[8];
    }
    for (size_t i=0;i<9;++i) rows.push_back({names[i],values[i],important});
  }
  *out=std::move(rows); return true;
}
std::string CssBackgroundSerialize(const std::vector<CssDeclarationValue>& rows, bool* important) {
  using namespace background_value;
  if (important) *important=false;
  const auto pending=std::find_if(rows.begin(),rows.end(),[](const auto& row){return row.name=="background";});
  if (pending!=rows.end() && std::none_of(rows.begin(),rows.end(),[](const auto& row){
      return std::find(std::begin(names),std::end(names),row.name)!=std::end(names);})) {
    if (important) *important=pending->important;
    return pending->value;
  }
  std::array<std::string,9> values;
  bool flag=false;
  for (size_t i=0;i<9;++i) {
    const auto row=std::find_if(rows.begin(),rows.end(),[&](const auto& r){return r.name==names[i];});
    if (row==rows.end() || (i && row->important!=flag)) return {};
    values[i]=row->value; flag=row->important;
  }
  if (important) *important=flag;
  if (std::any_of(values.begin(),values.end(),Wide)) {
    if (std::all_of(values.begin(),values.end(),[&](const auto& v){return v==values[0];})) return values[0];
    return {};
  }
  std::array<std::vector<std::string>,8> lists;
  for (size_t i=0;i<8;++i) lists[i]=CssSplit(values[i],',');
  const auto count=lists[0].size();
  if (!count || std::any_of(lists.begin(),lists.end(),[&](const auto& list){return list.size()!=count;})) return {};
  std::string result;
  for (size_t i=0;i<count;++i) {
    std::string layer;
    const auto add=[&](const std::string& value){if (!layer.empty()) layer+=' ';layer+=value;};
    if (lists[0][i]!="none") add(lists[0][i]);
    if (lists[4][i]!="repeat") add(lists[4][i]);
    if (lists[5][i]!="scroll") add(lists[5][i]);
    if (lists[1][i]!="0%" || lists[2][i]!="0%" || lists[3][i]!="auto") {
      add(lists[1][i]+" "+lists[2][i]);
      if (lists[3][i]!="auto") layer+=" / "+lists[3][i];
    }
    if (lists[6][i]!="padding-box" || lists[7][i]!="border-box") {
      add(lists[6][i]); if (lists[7][i]!=lists[6][i]) add(lists[7][i]);
    }
    if (i+1==count && values[8]!="rgba(0, 0, 0, 0)") add(values[8]);
    if (layer.empty()) layer="none";
    if (i) result+=", "; result+=layer;
  }
  return result;
}
std::string CssBackgroundComputed(const std::string& name,const std::string& input,const std::string& current,double em,double rem) {
  using namespace background_value;
  if (name!="background-position-x" && name!="background-position-y" && name!="background-size" && name!="background-image") return input;
  const auto length=[&](const std::string& text) {
    if (CssNumericParse(text).kind!=CssLength) return text;
    const auto number=CssNumericResolve(text,em,rem,0);
    return number.kind==CssLength?CssFloatText(float(number.number))+"px":text;
  };
  std::string result;
  for (const auto& part:CssSplit(input,',')) {
    std::string value=part;
    if (name=="background-image") {
      const auto open=part.find('(');
      if (open!=part.npos && CssLower(part.substr(0,open)).find("gradient")!=std::string::npos) {
        std::string args;
        for (const auto& stop:CssSplit(part.substr(open+1,part.size()-open-2),',')) {
          auto words=Tokens(stop);
          if (!words.empty() && CssColorSupported(words[0])) {
            const auto color=CssComputedColor(words[0],current);
            if (!color.empty()) words[0]=color;
          }
          if (!args.empty()) args+=", ";
          for (size_t i=0;i<words.size();++i) args+=(i?" ":"")+words[i];
        }
        value=part.substr(0,open+1)+args+")";
      }
      if (open!=part.npos && Word(CssLower(part.substr(0,open)),"image-set,-webkit-image-set")) {
        std::string args;
        for (const auto& choice:CssSplit(part.substr(open+1,part.size()-open-2),',')) {
          auto words=Tokens(choice);
          bool density=false;
          for (auto& word:words) {
            const auto number=CssNumericParse(word);
            if (number.kind!=CssResolution) continue;
            const auto lower=CssLower(word);
            const double scale=lower.ends_with("dpi")?1.0/96:lower.ends_with("dpcm")?2.54/96:1;
            word=CssFloatText(float(number.number*scale))+"dppx";density=true;
          }
          if (!density) words.push_back("1dppx");
          if (!args.empty()) args+=", ";
          for (size_t i=0;i<words.size();++i) args+=(i?" ":"")+words[i];
        }
        value=part.substr(0,open+1)+args+")";
      }
    } else {
      auto words=Tokens(CssLower(part));
      for (auto& word:words) word=length(word);
      if (name=="background-size") {
        value.clear();for (const auto& word:words) value+=(value.empty()?"":" ")+word;
      } else
      if (words.size()==1) {
        if (words[0]=="center") value="50%";
        else if (words[0]=="left" || words[0]=="top") value="0%";
        else if (words[0]=="right" || words[0]=="bottom") value="100%";
        else value=words[0];
      } else if (words.size()==2) {
        if (words[0]=="left" || words[0]=="top") value=words[1];
        else if (words[0]=="right" || words[0]=="bottom") value="calc(100% - "+words[1]+")";
      }
    }
    if (!result.empty()) result+=", ";
    result+=value;
  }
  return result;
}
}  // namespace ruyijs::domain::styling
