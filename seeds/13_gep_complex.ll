%struct.Point = type { i32, i32 }
%struct.Rect = type { %struct.Point, %struct.Point }

define i32 @test_gep(ptr %rect_ptr, i64 %idx) {
entry:
  %p2_y_ptr = getelementptr inbounds %struct.Rect, ptr %rect_ptr, i64 %idx, i32 1, i32 1
  %val = load i32, ptr %p2_y_ptr, align 4
  %add = add i32 %val, 1
  store i32 %add, ptr %p2_y_ptr, align 4
  ret i32 %add
}
