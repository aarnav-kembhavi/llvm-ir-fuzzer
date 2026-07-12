; Pattern: function call
declare i32 @external_func(i32)

define i32 @caller(i32 %x) {
entry:
  %call1 = call i32 @external_func(i32 %x)
  %add = add i32 %call1, 42
  %call2 = call i32 @external_func(i32 %add)
  ret i32 %call2
}
