; Pattern: memory
define i32 @memory_ops(ptr %ptr) {
entry:
  %val = load i32, ptr %ptr, align 4
  %add = add i32 %val, 10
  store i32 %add, ptr %ptr, align 4
  ret i32 %add
}
