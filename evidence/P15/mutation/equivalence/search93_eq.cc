// Equivalence check for search.cc:93 (index tokenizer: start <= size vs start < size).
#include <cstdio>
#include <random>
#include <string>
#include <vector>
static std::vector<std::string> Tokens(const std::string& low, bool orig) {
  std::vector<std::string> toks;
  size_t start = 0;
  while (orig ? (start <= low.size()) : (start < low.size())) {
    size_t end = low.find(' ', start);
    if (end == std::string::npos) end = low.size();
    const std::string tok = low.substr(start, end - start);
    if (!tok.empty()) toks.push_back(tok);
    if (end == low.size()) break;
    start = end + 1;
  }
  return toks;
}
int main() {
  std::mt19937 rng(20260911);
  const char alphabet[] = "ab c";
  unsigned long long cases = 0, mismatches = 0;
  for (int n = 0; n < 2000000; ++n) {
    std::string s;
    const int len = static_cast<int>(rng() % 9);
    for (int i = 0; i < len; ++i) s.push_back(alphabet[rng() % 4]);
    ++cases;
    if (Tokens(s, true) != Tokens(s, false)) ++mismatches;
  }
  std::printf("cases=%llu mismatches=%llu\n", cases, mismatches);
  return mismatches != 0;
}
