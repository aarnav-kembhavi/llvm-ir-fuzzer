define internal i32 @helper(i32 %x) {
entry:
  %mul = mul i32 %x, 3
  ret i32 %mul
}

define i32 @test_call(i32 %a, i32 %b) {
entry:
  %cmp = icmp sgt i32 %a, %b
  br i1 %cmp, label %if.then, label %if.else

if.then:
  %call1 = call i32 @helper(i32 %a)
  br label %return

if.else:
  %call2 = call i32 @helper(i32 %b)
  br label %return

return:
  %retval = phi i32 [ %call1, %if.then ], [ %call2, %if.else ]
  ret i32 %retval
}
