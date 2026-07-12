; Pattern: branch
define i32 @conditional_branch(i32 %x) {
entry:
  %cmp = icmp sgt i32 %x, 10
  br i1 %cmp, label %if.then, label %if.else

if.then:
  %add = add i32 %x, 5
  br label %if.end

if.else:
  %sub = sub i32 %x, 5
  br label %if.end

if.end:
  %res = phi i32 [ %add, %if.then ], [ %sub, %if.else ]
  ret i32 %res
}
