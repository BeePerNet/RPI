WARNING: This is not the best way to connect a motor to Raspberry PI.

Control an analog computer fan with PWM and read the RPM with only 3 wire: Power, ground and hall effect sensor.

For GPIO, we have to deal with that:

![Fan_PWM_piscope](https://user-images.githubusercontent.com/46988275/54840986-a0584e00-4ca4-11e9-8593-cf068c1db6b0.png)

To do the trick, I get milliseconds between bit switch when it happens after 5ms. This happens 4 times by rotation.

Schemas

![Fan_PWM_bb](https://user-images.githubusercontent.com/46988275/54840432-6c305d80-4ca3-11e9-8960-9d9df191c138.png)

![Fan_PWM_schéma](https://user-images.githubusercontent.com/46988275/54840433-6c305d80-4ca3-11e9-93e9-00b92c1430a5.png)
