; Pattern: nested loop
define i32 @nested_loop(i32 %n, i32 %m) {
entry:
  br label %outer.loop

outer.loop:
  %i = phi i32 [ 0, %entry ], [ %i.next, %outer.latch ]
  %sum = phi i32 [ 0, %entry ], [ %sum.next, %outer.latch ]
  br label %inner.loop

inner.loop:
  %j = phi i32 [ 0, %outer.loop ], [ %j.next, %inner.loop ]
  %inner.sum = phi i32 [ %sum, %outer.loop ], [ %inner.sum.next, %inner.loop ]
  
  %add = add i32 %i, %j
  %inner.sum.next = add i32 %inner.sum, %add
  %j.next = add i32 %j, 1
  
  %cmp.inner = icmp slt i32 %j.next, %m
  br i1 %cmp.inner, label %inner.loop, label %outer.latch

outer.latch:
  %sum.next = phi i32 [ %inner.sum.next, %inner.loop ]
  %i.next = add i32 %i, 1
  %cmp.outer = icmp slt i32 %i.next, %n
  br i1 %cmp.outer, label %outer.loop, label %exit

exit:
  ret i32 %sum.next
}
