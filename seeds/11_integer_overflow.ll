define i32 @test_overflow(i32 %a, i32 %b) {
entry:
  %add = add nsw i32 %a, %b
  %mul = mul nsw i32 %add, 2147483647
  %sub = sub nuw i32 %mul, 1
  ret i32 %sub
}
