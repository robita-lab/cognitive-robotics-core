//****************************************************************************************************
//        YOU TUBE - Alberto Tecnologia                                                             **
//                                                                                                  **
// Alberto Noboru Miyadaira                                                                         **
// www.albertonoboru.com.br                                                                         **
//                                                                                                  **
// Baud rate: 26315bps, 31250bps, 52630bps                                                          **
// Packet/Pacote: 0x100,LSB,MSB,LSB,MSB,0x055,0x058,0x058,0x000,0x0FE                               **
//                                                                                                  **
//Não se esqueça que é apenas um código de demonstração. Deve ser melhorado para maior segurança.   **
//Don't forget it's just a demo code. It must be improved for greater security.                     **
//                                                                                                  **
// Good luck with your projects                                                                     **
// Boa sorte com seus projetos                                                                      **
//                                                                                                  **
// Please keep the credits...                                                                       **
// Por favor, mantenha os créditos...                                                               **
//****************************************************************************************************

#define F_R 4     //0 - forward/frente
                  //1 - reverse/ré
                  
//*********************************************************************************************************
// If the pins are changed, the generated signals must be checked in the logic analyzer                  **
// Se os pinos forem alterados, os sinais gerados devem ser verificados no analisador lógico             **
//*********************************************************************************************************

#define TX_R 6   //Pin TX
#define TX_L 5   //Pin TX

//**********************************************************
//                 baud rate: 26315 bps                   **
//**********************************************************
//unsigned char TX_P = 107;       //Período de um bit - Period of one bit
//unsigned char TX_P1 = 107;      //Período de um bit - Period of one bit

//**********************************************************
//                 baud rate: 31250 bps                   **
//**********************************************************
//unsigned char TX_P = 80;       //Período de um bit - Period of one bit
//unsigned char TX_P1 = 80;      //Período de um bit - Period of one bit

//**********************************************************
//                 baud rate: 52630 bps                   **
//**********************************************************
unsigned char TX_P = 31;       //Período de um bit - Period of one bit
unsigned char TX_P1 = 26;      //Período de um bit - Period of one bit

unsigned char TX_P_STOP = 200; //Período do stop bit + delay- Period of stop bit + delay

int Throttle = 0;   //Acelerador 
int Speed = 0x0000; //Velocidade

void setup() 
{    
    pinMode(F_R, INPUT_PULLUP);
    pinMode(TX_R, OUTPUT);
    pinMode(TX_L, OUTPUT);
   
    digitalWrite(TX_R,1);
    digitalWrite(TX_L,1);  
}

void loop() 
{      
      Throttle = analogRead(A0); 

      // Throttle signal / Sinal acelareador = 820mV - 4250mV
      // ADC 10bits resol. 0 - 1023
      // Throttle/Acelerador < 250  - Motor OFF     
      if(Throttle<250) 
      {
        if(digitalRead(F_R)==1) //forward / frente 
            Speed = 0x0000;
        else                    //reverse / ré 
            Speed = 0xFFFF;          
      }
      else
      {
        // Throttle/Acelerador > 900 - Motor OFF
        if(Throttle>900)
        {
          if(digitalRead(F_R)==1) //forward/frente  
            Speed = 0x0000;
          else                    //reverse / ré 
            Speed = 0xFFFF;
        }
        else
        // Throttle/Acelerador > 250 e/and < 900 = Motor ON
        {
            Speed = map(Throttle,250,900,0x0030,0x06FF);
            
            if(digitalRead(F_R)==0)//reverse / ré
              Speed =~Speed;  
        }        
      }

      //**********************************************************
      //                 Start packet: 0x100                    **
      //**********************************************************

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP);
      
      //**********************************************************
      //               1º speed - velocidade                    **
      //**********************************************************
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P1);
      
      digitalWrite(TX_R,(Speed)&1);
      digitalWrite(TX_L,(Speed)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>1)&1);
      digitalWrite(TX_L,(Speed>>1)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>2)&1);
      digitalWrite(TX_L,(Speed>>2)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>3)&1);
      digitalWrite(TX_L,(Speed>>3)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>4)&1);
      digitalWrite(TX_L,(Speed>>4)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>5)&1);
      digitalWrite(TX_L,(Speed>>5)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>6)&1);
      digitalWrite(TX_L,(Speed>>6)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,(Speed>>7)&1);
      digitalWrite(TX_L,(Speed>>7)&1);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P1);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,(Speed>>8)&1);
      digitalWrite(TX_L,(Speed>>8)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>9)&1);
      digitalWrite(TX_L,(Speed>>9)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>10)&1);
      digitalWrite(TX_L,(Speed>>10)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>11)&1);
      digitalWrite(TX_L,(Speed>>11)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>12)&1);
      digitalWrite(TX_L,(Speed>>12)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>13)&1);
      digitalWrite(TX_L,(Speed>>13)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>14)&1);
      digitalWrite(TX_L,(Speed>>14)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>15)&1);
      digitalWrite(TX_L,(Speed>>15)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP);

      //**********************************************************
      //               2º speed - velocidade                    **
      //**********************************************************
       digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,(Speed)&1);
      digitalWrite(TX_L,(Speed)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>1)&1);
      digitalWrite(TX_L,(Speed>>1)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>2)&1);
      digitalWrite(TX_L,(Speed>>2)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>3)&1);
      digitalWrite(TX_L,(Speed>>3)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>4)&1);
      digitalWrite(TX_L,(Speed>>4)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>5)&1);
      digitalWrite(TX_L,(Speed>>5)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>6)&1);
      digitalWrite(TX_L,(Speed>>6)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>7)&1);
      digitalWrite(TX_L,(Speed>>7)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,(Speed>>8)&1);
      digitalWrite(TX_L,(Speed>>8)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>9)&1);
      digitalWrite(TX_L,(Speed>>9)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>10)&1);
      digitalWrite(TX_L,(Speed>>10)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>11)&1);
      digitalWrite(TX_L,(Speed>>11)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>12)&1);
      digitalWrite(TX_L,(Speed>>12)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>13)&1);
      digitalWrite(TX_L,(Speed>>13)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>14)&1);
      digitalWrite(TX_L,(Speed>>14)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,(Speed>>15)&1);
      digitalWrite(TX_L,(Speed>>15)&1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP); 
    
      /*if(Throttle<250)
      {
            //**********************************************************
            //                      Code: 0X0AA                       **
            //**********************************************************  
            //Hoverboard without auto-balance function / Hoverboard sem função de auto-equilíbrio
            //The main board does not energize the motor phases / A placa principal não energiza as fases do motor
            
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
            
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P_STOP);
      }
      else
      {*/
            //**********************************************************
            //                      Code: 0X055                       **
            //**********************************************************         
            //The main board drives the motor.   
            //A placa principal aciona o motor.

            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
            
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,0);
            digitalWrite(TX_L,0);
            _delay_loop_2(TX_P);
      
            digitalWrite(TX_R,1);
            digitalWrite(TX_L,1);
            _delay_loop_2(TX_P_STOP);         
      //}

      //**********************************************************
      //                      Code: 0X058                       **
      //********************************************************** 
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P_STOP);

      //**********************************************************
      //                      Code: 0X058                       **
      //**********************************************************
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);      
      _delay_loop_2(TX_P_STOP);

      //**********************************************************
      //                      Code: 0X000                       **
      //**********************************************************
        
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);      
      _delay_loop_2(TX_P_STOP);   
      
      //**********************************************************
      //                      Code: 0X0FE                       **
      //**********************************************************
             
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);
      
      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,0);
      digitalWrite(TX_L,0);
      _delay_loop_2(TX_P);

      digitalWrite(TX_R,1);
      digitalWrite(TX_L,1);      
      _delay_loop_2(TX_P_STOP);                 
}
