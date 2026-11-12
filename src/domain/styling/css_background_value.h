#pragma once
#include "domain/styling/css_declarations.h"
namespace ruyijs::domain::styling {
std::vector<std::string> CssBackgroundLonghands();
bool CssBackgroundExpand(const std::string&, bool, std::vector<CssDeclarationValue>*);
std::string CssBackgroundSerialize(const std::vector<CssDeclarationValue>&, bool* = nullptr);
bool CssBackgroundImage(const std::string&);
bool CssBackgroundLonghand(const std::string&, const std::string&);
bool CssBackgroundProperty(const std::string&);
bool CssBackgroundPositionExpand(const std::string&, bool, std::vector<CssDeclarationValue>*);
std::string CssBackgroundPositionSerialize(const std::vector<CssDeclarationValue>&, bool* = nullptr);
std::string CssBackgroundComputed(const std::string&, const std::string&, const std::string&);
}
