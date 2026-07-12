; Pattern: arithmetic
define i32 @arithmetic_ops(i32 %a, i32 %b) {
entry:
  %add = add i32 %a, %b
  %sub = sub i32 %add, 5
  %mul = mul i32 %sub, %b
  %div = sdiv i32 %mul, 2
  ret i32 %div
}
