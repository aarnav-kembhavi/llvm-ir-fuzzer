declare i32 @__gxx_personality_v0(...)
declare void @may_throw()

define i32 @test_invoke() personality ptr @__gxx_personality_v0 {
entry:
  invoke void @may_throw()
          to label %normal unwind label %catch

normal:
  ret i32 0

catch:
  %exn = landingpad { ptr, i32 }
          catch ptr null
  ret i32 1
}
