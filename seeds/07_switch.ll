; Pattern: switch
define i32 @switch_case(i32 %x) {
entry:
  switch i32 %x, label %default [
    i32 0, label %case0
    i32 1, label %case1
    i32 2, label %case2
  ]

case0:
  ret i32 10

case1:
  ret i32 20

case2:
  ret i32 30

default:
  ret i32 -1
}
