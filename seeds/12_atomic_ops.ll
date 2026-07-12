define i32 @test_atomic(ptr %ptr, i32 %val, i32 %cmp) {
entry:
  %old = atomicrmw add ptr %ptr, i32 %val seq_cst
  %pair = cmpxchg ptr %ptr, i32 %cmp, i32 %val seq_cst monotonic
  %success = extractvalue { i32, i1 } %pair, 1
  %ext = zext i1 %success to i32
  %res = add i32 %old, %ext
  ret i32 %res
}
