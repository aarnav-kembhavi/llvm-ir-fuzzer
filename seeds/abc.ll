; Pattern: custom
; custom-seed (added via dashboard)
define i32 @compute(i32 %n) {
entry:
  br label %loop

loop:
  %i = phi i32 [0, %entry], [%next, %loop]
  %acc = phi i32 [1, %entry], [%mul, %loop]

  %mul = mul nsw i32 %acc, 3
  %next = add i32 %i, 1
  %done = icmp eq i32 %next, %n

  br i1 %done, label %exit, label %loop

exit:
  ret i32 %mul
}
