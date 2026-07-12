; Pattern: struct
%Point = type { i32, i32 }

define i32 @struct_ops(ptr %p) {
entry:
  %x_ptr = getelementptr inbounds %Point, ptr %p, i32 0, i32 0
  %x_val = load i32, ptr %x_ptr, align 4
  
  %y_ptr = getelementptr inbounds %Point, ptr %p, i32 0, i32 1
  %y_val = load i32, ptr %y_ptr, align 4
  
  %add = add i32 %x_val, %y_val
  
  %new_x = mul i32 %add, 2
  store i32 %new_x, ptr %x_ptr, align 4
  
  ret i32 %add
}
