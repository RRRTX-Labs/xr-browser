// Equivalence check for cohort.cc:17 (acc = 0 vs acc = 1 before the 8-byte fold).
#include <cstdint>
#include <cstdio>
#include <random>
int main() {
  std::mt19937_64 rng(20260911);
  uint64_t mismatches = 0, total = 0;
  for (uint64_t n = 0; n < 2000000; ++n) {
    uint8_t d[32];
    for (auto& b : d) b = static_cast<uint8_t>(rng());
    uint64_t a0 = 0, a1 = 1;
    for (int i = 0; i < 8; ++i) { a0 = (a0 << 8) | d[i]; a1 = (a1 << 8) | d[i]; }
    for (int buckets = 1; buckets <= 100; buckets += 33) {
      ++total;
      if (a0 % buckets != a1 % buckets) ++mismatches;
    }
    if (a0 != a1) ++mismatches;
  }
  std::printf("total=%llu mismatches=%llu\n", (unsigned long long)total, (unsigned long long)mismatches);
  return mismatches != 0;
}
