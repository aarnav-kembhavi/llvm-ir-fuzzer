; Pattern: phi node
define i32 @complex_phi(i32 %x, i32 %y) {
entry:
  %cmp1 = icmp sgt i32 %x, 0
  br i1 %cmp1, label %bb1, label %bb2

bb1:
  %add = add i32 %x, 10
  br label %bb3

bb2:
  %sub = sub i32 %y, 5
  br label %bb3

bb3:
  %val1 = phi i32 [ %add, %bb1 ], [ %sub, %bb2 ]
  %cmp2 = icmp slt i32 %val1, 100
  br i1 %cmp2, label %bb4, label %bb5

bb4:
  %mul = mul i32 %val1, 2
  br label %exit

bb5:
  %div = sdiv i32 %val1, 2
  br label %exit

exit:
  %final = phi i32 [ %mul, %bb4 ], [ %div, %bb5 ]
  ret i32 %final
}
